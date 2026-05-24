"""Selector 结果校验、兜底策略与最终 Agent 列表确定。"""

import re
from ..schemas import (
    ArticleInput, ArticleSegment, SelectorResult, AgentSelection,
)
from ..agents.registry import AgentRegistry
from ..config import ReviewSettings

# 高风险关键词列表（从 risky_phrases 扫描或内置）
_SENSITIVE_PATTERNS = [
    "震惊", "曝光", "怒了", "所有人都", "必须看", "不看后悔",
    "彻底炸了", "投诉", "处分", "开除", "举报",
]
_INTERVIEW_PATTERNS = re.compile(r"采访|受访|他说|她表示|问[：:]|答[：:]")
_NOTICE_PATTERNS = re.compile(r"通知|公示|报名|截止|时间地点")
_ACTIVITY_PATTERNS = re.compile(r"活动|现场|参与者|举办")
_TITLE_RISK_PATTERNS = [
    "震惊", "曝光", "怒了", "所有人都", "必须看", "不看后悔",
    "彻底炸了",
]


def build_deterministic_hints(
    article: ArticleInput,
    segments: list[ArticleSegment],
) -> dict:
    """从稿件中提取确定性提示，辅助 Selector 判断。"""
    full_text = article.title + "\n" + article.body

    sensitive_found = [kw for kw in _SENSITIVE_PATTERNS if kw in full_text]

    return {
        "has_images": len(article.images) > 0,
        "paragraph_count": len([s for s in segments if s.kind == "body"]),
        "title_contains_question_mark": "?" in article.title or "？" in article.title,
        "possible_interview": bool(_INTERVIEW_PATTERNS.search(full_text)),
        "possible_notice": bool(_NOTICE_PATTERNS.search(full_text)),
        "possible_activity": bool(_ACTIVITY_PATTERNS.search(full_text)),
        "title_risk": any(kw in article.title for kw in _TITLE_RISK_PATTERNS),
        "sensitive_keywords_found": sensitive_found,
        "article_type_guess_by_rules": _guess_article_type(full_text),
    }


def _guess_article_type(text: str) -> str:
    """基于规则猜测稿件类型。"""
    if _INTERVIEW_PATTERNS.search(text):
        return "interview"
    if _NOTICE_PATTERNS.search(text):
        return "notice"
    if _ACTIVITY_PATTERNS.search(text):
        return "activity"
    return "news"


def validate_selector_result(
    result: SelectorResult,
    registry: AgentRegistry,
    article: ArticleInput,
    settings: ReviewSettings,
) -> SelectorResult:
    """校验并清洗 Selector 输出。

    校验规则：
    1. agent_id 必须存在且非 selector。
    2. Agent 必须 enabled 且 kind 为 reviewer。
    3. applies_to 必须匹配。
    4. 去重。
    5. 不超过 max_selected_agents。
    """
    validated: list[AgentSelection] = []
    seen: set[str] = set()
    warnings = list(result.warnings)

    for sel in result.selected_agents:
        aid = sel.agent_id

        if aid in seen:
            continue
        seen.add(aid)

        if aid == "selector":
            warnings.append(f"Selector 不能选择自身（{aid}），已跳过")
            continue

        if not registry.exists(aid):
            warnings.append(f"Agent {aid} 不存在，已跳过")
            continue

        agent = registry.get(aid)
        if not agent.enabled:
            warnings.append(f"Agent {aid} 已禁用，已跳过")
            continue

        if agent.kind != "reviewer":
            warnings.append(f"Agent {aid} 的 kind 不是 reviewer，已跳过")
            continue

        if not _check_applies_to(agent, article):
            warnings.append(f"Agent {aid} 不适用于稿件类型 {article.article_type}，已跳过")
            continue

        validated.append(sel)

    # 限制数量
    if len(validated) > settings.max_selected_agents:
        warnings.append(
            f"选中 Agent 数量 ({len(validated)}) 超过上限 ({settings.max_selected_agents})，"
            f"已截断"
        )
        validated = validated[:settings.max_selected_agents]

    result.selected_agents = validated
    result.warnings = warnings
    return result


def _check_applies_to(agent, article: ArticleInput) -> bool:
    """检查 Agent 的 applies_to 是否匹配稿件。"""
    at = agent.applies_to

    types_ok = "*" in at.article_types or article.article_type in at.article_types
    if not types_ok:
        return False

    if at.columns:
        cols_ok = "*" in at.columns or (article.column or "") in at.columns
        if not cols_ok:
            return False

    return True


def fallback_select_agents(
    article: ArticleInput,
    hints: dict,
    registry: AgentRegistry,
    settings: ReviewSettings,
) -> list[str]:
    """兜底策略：代码层选择基础 Agent 组合。"""
    selected: set[str] = set()

    # 兜底时始终包含基础 Agent
    for aid in settings.base_agent_ids:
        if registry.exists(aid) and registry.get(aid).enabled:
            selected.add(aid)

    if hints.get("has_images"):
        for aid in ["copyright_reviewer", "privacy_reviewer"]:
            if registry.exists(aid) and registry.get(aid).enabled:
                selected.add(aid)

    if hints.get("possible_interview"):
        if registry.exists("interview_ethics_reviewer") and registry.get("interview_ethics_reviewer").enabled:
            selected.add("interview_ethics_reviewer")

    if hints.get("title_risk"):
        if registry.exists("title_reviewer") and registry.get("title_reviewer").enabled:
            selected.add("title_reviewer")

    return list(selected)


def finalize_selected_agents(
    selector_result: SelectorResult,
    article: ArticleInput,
    hints: dict,
    registry: AgentRegistry,
    settings: ReviewSettings,
) -> list[str]:
    """最终确定启用的 Agent 列表：合并 Selector 结果 + 基础兜底 Agent。"""
    agent_ids: list[str] = []

    if selector_result.status == "success":
        for sel in selector_result.selected_agents:
            if sel.agent_id not in agent_ids:
                agent_ids.append(sel.agent_id)

    # 补充基础 Agent
    if settings.always_include_base_agents:
        for aid in settings.base_agent_ids:
            if aid not in agent_ids and registry.exists(aid) and registry.get(aid).enabled:
                agent_ids.append(aid)

    # 如果仍然为空，走兜底
    if not agent_ids:
        agent_ids = fallback_select_agents(article, hints, registry, settings)

    return agent_ids
