"""Selector 校验和路由测试。"""

from review_tool.schemas import (
    ArticleInput, SelectorResult, AgentSelection, AgentConfig,
)
from review_tool.agents.registry import AgentRegistry
from review_tool.config import ReviewSettings
from review_tool.review.routing import (
    build_deterministic_hints,
    validate_selector_result,
    fallback_select_agents,
    finalize_selected_agents,
)


def _make_registry(agent_ids: list[str] | None = None) -> AgentRegistry:
    """构建测试用 AgentRegistry。"""
    if agent_ids is None:
        agent_ids = ["selector", "fact_checker", "risk_reviewer", "privacy_reviewer",
                     "audience_reviewer", "format_reviewer", "title_reviewer"]

    configs = []
    for aid in agent_ids:
        configs.append(AgentConfig(
            agent_id=aid,
            name=aid,
            enabled=True,
            kind="selector" if aid == "selector" else "reviewer",
            priority={"selector": 100, "risk_reviewer": 90, "privacy_reviewer": 85,
                      "fact_checker": 80, "audience_reviewer": 60, "format_reviewer": 50,
                      "title_reviewer": 70}.get(aid, 50),
        ))
    return AgentRegistry(configs)


def test_deterministic_hints():
    article = ArticleInput(
        title="震惊！校园发生大事",
        body="采访了张同学，他表示活动很有趣。活动现场参与者众多。",
        images=["a.jpg"],
    )
    hints = build_deterministic_hints(article, [])
    assert hints["has_images"] is True
    assert hints["possible_interview"] is True
    assert hints["possible_activity"] is True
    assert hints["title_risk"] is True
    assert len(hints["sensitive_keywords_found"]) > 0


def test_validate_selector_result_rejects_self():
    registry = _make_registry()
    article = ArticleInput(body="test")
    result = SelectorResult(
        selected_agents=[AgentSelection(agent_id="selector", reason="...")],
    )
    settings = ReviewSettings()
    validated = validate_selector_result(result, registry, article, settings)
    assert len(validated.selected_agents) == 0


def test_validate_selector_result_rejects_unknown():
    registry = _make_registry()
    article = ArticleInput(body="test")
    result = SelectorResult(
        selected_agents=[AgentSelection(agent_id="nonexistent", reason="...")],
    )
    settings = ReviewSettings()
    validated = validate_selector_result(result, registry, article, settings)
    assert len(validated.selected_agents) == 0


def test_validate_selector_result_deduplicates():
    registry = _make_registry()
    article = ArticleInput(body="test")
    result = SelectorResult(
        selected_agents=[
            AgentSelection(agent_id="fact_checker", reason="a"),
            AgentSelection(agent_id="fact_checker", reason="b"),
        ],
    )
    settings = ReviewSettings()
    validated = validate_selector_result(result, registry, article, settings)
    assert len(validated.selected_agents) == 1


def test_fallback_select_agents():
    registry = _make_registry()
    article = ArticleInput(body="test")
    hints = {"has_images": True, "possible_interview": False, "title_risk": False}
    settings = ReviewSettings()
    selected = fallback_select_agents(article, hints, registry, settings)
    assert "fact_checker" in selected or len(selected) > 0


def test_finalize_selected_agents_adds_base():
    registry = _make_registry()
    article = ArticleInput(body="test")
    hints = {}
    settings = ReviewSettings(always_include_base_agents=True)

    result = SelectorResult(
        selected_agents=[AgentSelection(agent_id="title_reviewer", reason="test")],
    )
    selected = finalize_selected_agents(result, article, hints, registry, settings)
    # 应该包含 Selector 选的 + base agents
    assert "title_reviewer" in selected
    assert "fact_checker" in selected


def test_finalize_selected_agents_fallback_when_empty():
    # 使用包含 base agent IDs 的 registry
    agent_ids = ["selector", "fact_checker", "risk_reviewer", "audience_reviewer",
                 "format_reviewer", "privacy_reviewer"]
    configs = []
    for aid in agent_ids:
        configs.append(AgentConfig(
            agent_id=aid,
            name=aid,
            enabled=True,
            kind="selector" if aid == "selector" else "reviewer",
            priority=50,
        ))
    registry = AgentRegistry(configs)

    article = ArticleInput(body="test")
    hints = {}
    settings = ReviewSettings(always_include_base_agents=False)

    result = SelectorResult(selected_agents=[])
    selected = finalize_selected_agents(result, article, hints, registry, settings)
    # empty SelectorResult with always_include_base_agents=False triggers fallback
    # fallback checks base_agent_ids which are in the registry
    assert len(selected) > 0
