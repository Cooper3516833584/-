"""审稿引擎：串联所有模块的顶层入口。"""

import json
import re
from pathlib import Path
from .schemas import (
    ArticleInput, AgentSelection, ReviewRunResult, SelectorResult, make_run_id,
)
from .config import ReviewSettings, load_settings
from .loaders.agent_loader import load_agent_configs
from .loaders.corpus_loader import load_corpus
from .agents.registry import AgentRegistry
from .knowledge.chunker import chunk_documents
from .knowledge.retriever import KnowledgeRetriever
from .knowledge.keyword_extractor import build_retrieval_query
from .knowledge.index_cache import load_cache, save_cache
from .llm.base import LLMClient
from .llm.mock_client import MockLLMClient
from .llm.openai_client import OpenAIClient
from .review.preprocess import load_article_file, preprocess_article
from .review.routing import (
    build_deterministic_hints,
    validate_selector_result,
    fallback_select_agents,
    finalize_selected_agents,
)
from .review.executor import run_review_agents
from .review.validator import validate_agent_results
from .review.merger import collect_findings, merge_findings
from .review.report_builder import build_final_report
from .agents.selector import run_selector
from .exporters.json_exporter import export_json
from .exporters.docx_exporter import export_docx

WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def build_review_output_paths(article: ArticleInput, output_dir: Path, run_id: str) -> tuple[Path, Path, Path]:
    """生成本次审稿输出目录、DOCX 路径和 JSON 路径。"""
    title = _safe_output_name(article.title) or run_id
    stem = f"{title}_审查结果"
    run_dir = output_dir.resolve() / stem
    return (
        run_dir,
        run_dir / f"{stem}.docx",
        run_dir / "report.json",
    )


def build_llm_client(settings: ReviewSettings) -> LLMClient:
    """根据配置构建 LLM 客户端。"""
    if settings.mock_mode:
        return MockLLMClient()
    return OpenAIClient(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


class ReviewEngine:
    """审稿引擎：初始化和执行审稿的顶层入口。"""

    def __init__(self, project_root: Path | None = None, settings: ReviewSettings | None = None):
        self.project_root = (project_root or Path(".")).resolve()
        self.settings = settings or load_settings(self.project_root)

        # 加载 Agent 配置
        agent_dir = self.project_root / "agents"
        if not agent_dir.exists():
            raise FileNotFoundError(f"agents/ 目录不存在: {agent_dir}")
        self.agent_configs = load_agent_configs(agent_dir)
        self._apply_runtime_defaults()
        self.registry = AgentRegistry(self.agent_configs)

        # 加载知识库（优先使用缓存）
        self.chunks = load_cache(self.project_root)
        if self.chunks is None:
            documents = load_corpus(self.project_root)
            self.chunks = chunk_documents(documents)
            save_cache(self.project_root, self.chunks)
        self.retriever = KnowledgeRetriever(self.chunks)

        # LLM 客户端
        self.llm_client = build_llm_client(self.settings)

    def _apply_runtime_defaults(self) -> None:
        for config in self.agent_configs:
            config.model.name = self.settings.default_model_name
            config.model.temperature = self.settings.default_temperature
            config.model.timeout_seconds = self.settings.default_timeout_seconds
            config.model.max_retries = self.settings.default_max_retries
            config.output_schema = (
                self.settings.selector_output_schema
                if config.kind == "selector"
                else self.settings.reviewer_output_schema
            )

    async def review_file(
        self,
        article_path: Path,
        output_dir: Path | None = None,
        manual_agent_ids: list[str] | None = None,
    ) -> ReviewRunResult:
        """从文件路径审稿。"""
        article = load_article_file(article_path)
        article.source_path = str(article_path.resolve())
        return await self.review_article(article, output_dir, manual_agent_ids)

    async def review_article(
        self,
        article: ArticleInput,
        output_dir: Path | None = None,
        manual_agent_ids: list[str] | None = None,
    ) -> ReviewRunResult:
        """执行完整审稿流程。"""
        run_id = make_run_id()
        odir = (output_dir or self.project_root / "output").resolve()
        run_dir, report_docx_path, report_json_path = build_review_output_paths(article, odir, run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        warnings: list[str] = []
        errors: list[dict] = []

        # 1. 保存稿件快照
        _save_article_snapshot(article, run_dir)

        # 2. 预处理
        segments = preprocess_article(article)

        # 3. 构建 hints
        hints = build_deterministic_hints(article, segments)

        # 4. 运行 Selector 或使用手动 Agent 列表
        selector_result = SelectorResult(status="failed")
        fallback_used = False
        if manual_agent_ids is not None:
            selected_agent_ids, manual_warnings = self._resolve_manual_agent_ids(manual_agent_ids)
            warnings.extend(manual_warnings)
            selector_result = SelectorResult(
                status="success",
                detected_article_type=article.article_type,
                selected_agents=[
                    AgentSelection(
                        agent_id=agent_id,
                        reason="手动选择",
                        priority=self.registry.get(agent_id).priority,
                    )
                    for agent_id in selected_agent_ids
                ],
                reasoning_summary="本次由用户手动选择审稿 Agent。",
            )
        else:
            try:
                selector_result, selector_debug = await run_selector(
                    article=article,
                    segments=segments,
                    hints=hints,
                    registry=self.registry,
                    llm_client=self.llm_client,
                    settings=self.settings,
                )
                _save_debug(run_dir, "selector_debug.json", selector_debug)
            except Exception as e:
                warnings.append(f"Selector Agent 失败: {e}")
                errors.append({"stage": "selector", "error_type": type(e).__name__, "message": str(e), "detail": {}})

            # 5. 校验 Selector 结果
            try:
                selector_result = validate_selector_result(
                    selector_result, self.registry, article, self.settings
                )
            except Exception as e:
                warnings.append(f"Selector 校验失败: {e}")

            # 6. 确定最终 Agent 列表
            selected_agent_ids = finalize_selected_agents(
                selector_result=selector_result,
                article=article,
                hints=hints,
                registry=self.registry,
                settings=self.settings,
            )

            if selector_result.status == "failed" or not selector_result.selected_agents:
                fallback_used = True
                fallback_ids = fallback_select_agents(article, hints, self.registry, self.settings)
                for aid in fallback_ids:
                    if aid not in selected_agent_ids:
                        selected_agent_ids.append(aid)
                if fallback_used:
                    if selector_result.status == "failed":
                        warnings.append("Selector Agent 失败，已使用兜底 Agent 组合。")
                    else:
                        warnings.append("Selector 未选择 Agent，已使用兜底 Agent 组合。")

        # 7. 知识检索
        retrieval_query = build_retrieval_query(article, segments, selector_result, hints)
        retrieved_context = self.retriever.retrieve(
            query=retrieval_query.query_text,
            tags=retrieval_query.tags,
            preferred_sources=retrieval_query.preferred_sources,
            top_k=self.settings.retrieval_top_k,
        )

        if not retrieved_context:
            warnings.append("本次未加载到本地知识材料。")

        # 8. 并行运行审稿 Agent
        agent_results = await run_review_agents(
            agent_ids=selected_agent_ids,
            registry=self.registry,
            article=article,
            segments=segments,
            retrieved_context=retrieved_context,
            llm_client=self.llm_client,
            settings=self.settings,
        )

        failed_agents = [r for r in agent_results if r.status != "success"]
        for fa in failed_agents:
            warnings.append(f"Agent {fa.agent_id} ({fa.agent_name}) 状态: {fa.status} - {fa.error_message or '无详情'}")

        # 9. 构建报告
        final_report, merged_findings = build_final_report(
            article=article,
            selector_result=selector_result,
            selected_agent_ids=selected_agent_ids,
            retrieved_context=retrieved_context,
            agent_results=agent_results,
            warnings=warnings,
            errors=errors,
        )

        # 10. 组装结果
        result = ReviewRunResult(
            run_id=run_id,
            article=article,
            segments=segments,
            selector_result=selector_result,
            selected_agent_ids=selected_agent_ids,
            retrieved_context=retrieved_context,
            agent_results=agent_results,
            merged_findings=merged_findings,
            final_report=final_report,
            errors=errors,
            warnings=warnings,
        )

        # 11. 导出
        export_json(result, report_json_path)
        export_docx(result, report_docx_path)

        # 保存中间文件
        _save_json(run_dir / "selector_result.json", selector_result.model_dump())
        _save_json(run_dir / "agent_results.json", [r.model_dump() for r in agent_results])
        _save_json(run_dir / "retrieved_context.json", [
            {"chunk_id": c.chunk_id, "doc_id": c.doc_id, "source_type": c.source_type, "title": c.title, "score": c.score}
            for c in retrieved_context
        ])

        return result

    def _resolve_manual_agent_ids(self, agent_ids: list[str]) -> tuple[list[str], list[str]]:
        selected: list[str] = []
        warnings: list[str] = []

        for agent_id in agent_ids:
            if agent_id in selected:
                continue
            if not self.registry.exists(agent_id):
                warnings.append(f"手动选择的 Agent 不存在，已跳过: {agent_id}")
                continue
            agent = self.registry.get(agent_id)
            if not agent.enabled:
                warnings.append(f"手动选择的 Agent 未启用，已跳过: {agent_id}")
                continue
            if agent.kind not in {"reviewer", "persona"}:
                warnings.append(f"手动选择的 Agent 不是 reviewer/persona，已跳过: {agent_id}")
                continue
            selected.append(agent_id)

        if not selected:
            raise ValueError("手动模式至少需要选择一个已启用的审稿 Agent")

        return selected, warnings


def _save_article_snapshot(article: ArticleInput, run_dir: Path) -> None:
    background = (
        f"\n\n## 事件背景\n\n{article.event_background}"
        if article.event_background else ""
    )
    (run_dir / "article_snapshot.md").write_text(
        f"# {article.title}{background}\n\n{article.body}",
        encoding="utf-8",
    )


def _safe_output_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip(" ._")
    if not cleaned:
        cleaned = "未命名稿件"
    if cleaned.upper() in WINDOWS_RESERVED_FILENAMES:
        cleaned = f"{cleaned}_稿件"
    return cleaned[:80].strip(" ._") or "未命名稿件"


def _save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_debug(run_dir: Path, filename: str, data) -> None:
    debug_dir = run_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / filename).write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
