"""Agent 加载和 Registry 测试。"""

import tempfile
from pathlib import Path
from review_tool.loaders.agent_loader import load_agent_configs
from review_tool.agents.registry import AgentRegistry


def _write_agent(dir_path: Path, filename: str, frontmatter: str, body: str = "Prompt body"):
    (dir_path / filename).write_text(
        f"---\n{frontmatter}\n---\n{body}", encoding="utf-8"
    )


def test_load_minimal_agents():
    with tempfile.TemporaryDirectory() as tmp:
        agent_dir = Path(tmp)
        _write_agent(agent_dir, "00_selector.txt", "agent_id: selector\nname: 选择器\nenabled: true\nkind: selector\npriority: 100")
        _write_agent(agent_dir, "fact_checker.txt", "agent_id: fact_checker\nname: 事实核查\nenabled: true\nkind: reviewer")

        configs = load_agent_configs(agent_dir)
        assert len(configs) == 2

        # selector 排第一（priority 100 > 50）
        assert configs[0].agent_id == "selector"
        assert configs[1].agent_id == "fact_checker"


def test_missing_selector_raises():
    with tempfile.TemporaryDirectory() as tmp:
        agent_dir = Path(tmp)
        _write_agent(agent_dir, "fact_checker.txt", "agent_id: fact_checker\nname: 核查\nenabled: true\nkind: reviewer")

        try:
            load_agent_configs(agent_dir)
            assert False
        except ValueError as e:
            assert "selector" in str(e).lower()


def test_duplicate_agent_id_raises():
    with tempfile.TemporaryDirectory() as tmp:
        agent_dir = Path(tmp)
        _write_agent(agent_dir, "00_selector.txt", "agent_id: selector\nname: S\nenabled: true\nkind: selector")
        _write_agent(agent_dir, "01_dup.txt", "agent_id: selector\nname: S2\nenabled: true\nkind: reviewer")

        try:
            load_agent_configs(agent_dir)
            assert False
        except ValueError as e:
            assert "重复" in str(e) or "duplicate" in str(e).lower()


def test_selector_must_be_enabled():
    with tempfile.TemporaryDirectory() as tmp:
        agent_dir = Path(tmp)
        _write_agent(agent_dir, "00_selector.txt", "agent_id: selector\nname: S\nenabled: false\nkind: selector")

        try:
            load_agent_configs(agent_dir)
            assert False
        except ValueError as e:
            assert "enabled" in str(e).lower()


def test_registry_build_catalog():
    with tempfile.TemporaryDirectory() as tmp:
        agent_dir = Path(tmp)
        _write_agent(agent_dir, "00_selector.txt", "agent_id: selector\nname: 选择器\nenabled: true\nkind: selector\npriority: 100")
        _write_agent(agent_dir, "risk.txt", "agent_id: risk_reviewer\nname: 风险\nenabled: true\nkind: reviewer\npriority: 90\ncapabilities:\n  - risk")

        configs = load_agent_configs(agent_dir)
        registry = AgentRegistry(configs)
        catalog = registry.build_catalog_for_selector()

        assert len(catalog) == 1
        assert catalog[0]["agent_id"] == "risk_reviewer"
        assert "prompt_body" not in catalog[0]


def test_registry_list_enabled_reviewers():
    with tempfile.TemporaryDirectory() as tmp:
        agent_dir = Path(tmp)
        _write_agent(agent_dir, "00_selector.txt", "agent_id: selector\nname: S\nenabled: true\nkind: selector")
        _write_agent(agent_dir, "a.txt", "agent_id: a1\nname: A\nenabled: true\nkind: reviewer")
        _write_agent(agent_dir, "b.txt", "agent_id: b1\nname: B\nenabled: false\nkind: reviewer")

        configs = load_agent_configs(agent_dir)
        registry = AgentRegistry(configs)

        reviewers = registry.list_enabled_reviewers()
        assert len(reviewers) == 1
        assert reviewers[0].agent_id == "a1"
