"""立场画像模拟 Agent 测试。"""

from pathlib import Path

from review_tool.agents.prompt_builder import build_reviewer_prompt
from review_tool.agents.registry import AgentRegistry
from review_tool.loaders.agent_loader import load_agent_configs
from review_tool.review.routing import validate_selector_result
from review_tool.schemas import (
    AgentConfig,
    AgentSelection,
    ArticleInput,
    SelectorResult,
)
from review_tool.config import ReviewSettings
from review_tool.web_app import _create_agent


def test_persona_prompt_includes_custom_mindset():
    agent = AgentConfig(
        agent_id="persona_test",
        name="怀疑读者",
        kind="persona",
        metadata={
            "persona_profile": {
                "mindset": "你对所有报道都持怀疑态度，会优先找漏洞。",
                "stance": "怀疑",
                "thinking_style": "先质疑再阅读",
                "concerns": ["信任", "漏洞"],
            }
        },
    )

    system, _ = build_reviewer_prompt(
        agent,
        ArticleInput(title="测试", body="正文"),
        [],
        [],
    )

    assert "立场画像模拟 Agent" in system
    assert "你对所有报道都持怀疑态度" in system
    assert "不要把主观感受包装成事实结论" in system


def test_selector_validation_accepts_persona_agent():
    registry = AgentRegistry(
        [
            AgentConfig(agent_id="selector", name="选择器", kind="selector"),
            AgentConfig(agent_id="persona_test", name="怀疑读者", kind="persona"),
        ]
    )
    result = SelectorResult(
        selected_agents=[AgentSelection(agent_id="persona_test", reason="模拟读者反应")]
    )

    validated = validate_selector_result(
        result,
        registry,
        ArticleInput(title="测试", body="正文"),
        ReviewSettings(),
    )

    assert [item.agent_id for item in validated.selected_agents] == ["persona_test"]


def test_create_persona_agent_writes_profile(tmp_path: Path):
    agent_dir = tmp_path / "agents"
    agent_dir.mkdir()
    (agent_dir / "00_selector_agent.txt").write_text(
        "---\nagent_id: selector\nname: 选择器\nenabled: true\nkind: selector\n---\n",
        encoding="utf-8",
    )

    _create_agent(
        tmp_path,
        {
            "agent_id": "persona_custom",
            "name": "找茬读者",
            "kind": "persona",
            "priority": 30,
            "max_findings": 4,
            "capabilities": ["persona_response"],
            "persona_mindset": "你很讨厌这个校园媒体，总想找茬攻击。",
            "review_focus": "",
            "enabled": True,
        },
    )

    configs = load_agent_configs(agent_dir)
    created = next(item for item in configs if item.agent_id == "persona_custom")

    assert created.kind == "persona"
    assert created.metadata["persona_profile"]["mindset"] == "你很讨厌这个校园媒体，总想找茬攻击。"
