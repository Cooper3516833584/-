"""Selector Agent：自动判断稿件类型并选择审稿 Agent。"""

import json
from ..schemas import (
    ArticleInput, ArticleSegment, AgentConfig, SelectorResult, SelectorInput,
)
from ..agents.registry import AgentRegistry
from ..llm.base import LLMClient
from ..llm.structured import call_with_schema
from ..config import ReviewSettings


async def run_selector(
    article: ArticleInput,
    segments: list[ArticleSegment],
    hints: dict,
    registry: AgentRegistry,
    llm_client: LLMClient,
    settings: ReviewSettings,
) -> tuple[SelectorResult, dict]:
    """运行 Selector Agent，返回 (SelectorResult, debug_info)。"""
    selector_config = registry.get_selector()
    catalog = registry.build_catalog_for_selector()

    selector_input = SelectorInput(
        article=article,
        segments=segments,
        agent_catalog=catalog,
        deterministic_hints=hints,
    )

    system_prompt = _build_selector_system(selector_config)
    user_prompt = _build_selector_user(selector_input)

    debug = {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "catalog_size": len(catalog),
    }

    try:
        result, response = await call_with_schema(
            llm_client=llm_client,
            system=system_prompt,
            user=user_prompt,
            schema_model=SelectorResult,
            model=selector_config.model.name,
            temperature=selector_config.model.temperature,
            timeout_seconds=selector_config.model.timeout_seconds,
            max_retries=selector_config.model.max_retries,
        )
        debug["raw_output"] = response.text
        debug["token_usage"] = response.token_usage
        debug["latency_ms"] = response.latency_ms
        return result, debug

    except Exception as e:
        debug["error"] = str(e)
        return SelectorResult(
            status="failed",
            warnings=[f"Selector Agent 调用失败: {e}"],
        ), debug


def _build_selector_system(config: AgentConfig) -> str:
    return f"""{config.prompt_body}

你必须输出 JSON，不得输出 Markdown 代码块的前后缀。
只输出符合 SelectorResult schema 的 JSON 对象。
不得编造不存在的 Agent ID。
不选择 disabled Agent。
不输出具体修改意见。"""


def _build_selector_user(selector_input: SelectorInput) -> str:
    catalog_json = json.dumps(selector_input.agent_catalog, ensure_ascii=False, indent=2)
    hints_json = json.dumps(selector_input.deterministic_hints, ensure_ascii=False, indent=2)

    segments_text = "\n".join(
        f"[{s.segment_id}] {s.text}" for s in selector_input.segments[:20]
    )

    return f"""# 稿件信息

标题: {selector_input.article.title}
栏目: {selector_input.article.column or '未知'}
原始标注类型: {selector_input.article.article_type}
图片数量: {len(selector_input.article.images)}

# 稿件正文分段（前20段）

{segments_text}

# 代码预分析提示

{hints_json}

# 可用 Agent 目录

{catalog_json}

# 任务

根据以上信息，选择本次审稿应当启用的 Agent。请输出 SelectorResult JSON。"""
