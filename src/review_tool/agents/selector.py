"""Selector Agent：自动判断稿件类型并选择审稿 Agent。"""

import json
from ..schemas import (
    ArticleInput, ArticleSegment, AgentConfig, AgentSelection, SelectorResult, SelectorInput,
)
from ..agents.registry import AgentRegistry
from ..llm.base import LLMClient
from ..llm.structured import call_with_schema
from ..llm.json_repair import extract_json_text
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
        result = _coerce_selector_shorthand(result, response.text, registry)
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
必须使用 selected_agents 数组，不要输出 agent_ids 简写。
selected_agents 中每一项必须包含 agent_id、reason、priority。
可用 Agent 中 kind=reviewer 表示规则审查，kind=persona 表示模拟某类读者或利益相关者的立场反应。
当稿件可能存在误读、攻击、反感、信任下降或传播争议时，可以选择 persona Agent。
不得编造不存在的 Agent ID。
不选择 disabled Agent。
不输出具体修改意见。

输出格式示例：
{{
  "status": "success",
  "detected_article_type": "news",
  "detected_tags": ["campus_media"],
  "selected_agents": [
    {{"agent_id": "fact_checker", "reason": "需要核查事实与逻辑", "priority": 80}}
  ],
  "context_queries": ["事实核查", "校园媒体审稿"],
  "reasoning_summary": "选择理由摘要",
  "warnings": []
}}"""


def _build_selector_user(selector_input: SelectorInput) -> str:
    catalog_json = json.dumps(selector_input.agent_catalog, ensure_ascii=False, indent=2)
    hints_json = json.dumps(selector_input.deterministic_hints, ensure_ascii=False, indent=2)

    segments_text = "\n".join(
        f"[{s.segment_id}] {s.text}" for s in selector_input.segments[:20]
    )

    return f"""# 稿件信息

标题: {selector_input.article.title}
原始标注类型: {selector_input.article.article_type}
事件背景: {selector_input.article.event_background or '未填写'}
图片数量: {len(selector_input.article.images)}

# 稿件正文分段（前20段）

{segments_text}

# 代码预分析提示

{hints_json}

# 可用 Agent 目录

{catalog_json}

# 任务

根据以上信息，选择本次审稿应当启用的 Agent。请输出 SelectorResult JSON。"""


def _coerce_selector_shorthand(
    result: SelectorResult,
    raw_output: str,
    registry: AgentRegistry,
) -> SelectorResult:
    """兼容模型返回的 agent_ids 简写，转换成标准 selected_agents。"""
    if result.selected_agents:
        return result

    try:
        data = json.loads(extract_json_text(raw_output))
    except Exception:
        return result

    raw_agents = data.get("agent_ids") or data.get("selected_agent_ids") or data.get("agents")
    if not isinstance(raw_agents, list):
        return result

    selections: list[AgentSelection] = []
    for item in raw_agents:
        if isinstance(item, dict):
            agent_id = str(item.get("agent_id") or item.get("id") or "").strip()
            reason = str(item.get("reason") or "Selector 简写选择").strip()
            priority_value = item.get("priority")
        else:
            agent_id = str(item).strip()
            reason = "Selector 简写选择"
            priority_value = None

        if not agent_id:
            continue

        selections.append(
            AgentSelection(
                agent_id=agent_id,
                reason=reason,
                priority=_coerce_priority(priority_value, registry, agent_id),
            )
        )

    if not selections:
        return result

    result.selected_agents = selections
    if not result.reasoning_summary:
        result.reasoning_summary = "Selector 返回 agent_ids 简写，系统已自动转换为标准 selected_agents。"
    return result


def _coerce_priority(value, registry: AgentRegistry, agent_id: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        if registry.exists(agent_id):
            return registry.get(agent_id).priority
        return 50
