"""Schema 单元测试。"""

from review_tool.schemas import (
    ArticleInput, ArticleSegment, AgentConfig, KnowledgeDocument,
    KnowledgeChunk, SelectorResult, AgentSelection, Finding,
    AgentResult, ReviewRunResult, make_finding_id, make_run_id,
)


def test_article_input_minimal():
    a = ArticleInput(body="正文内容")
    assert a.title == ""
    assert a.body == "正文内容"
    assert a.article_type == "unknown"


def test_article_input_full():
    a = ArticleInput(
        title="测试标题",
        body="正文",
        author="作者",
        column="校园生活",
        article_type="news",
        event_background="活动发生在迎新周。",
        images=["a.jpg"],
    )
    assert a.title == "测试标题"
    assert a.article_type == "news"
    assert a.event_background == "活动发生在迎新周。"


def test_article_segment():
    s = ArticleSegment(segment_id="s001", index=0, kind="body", text="段落")
    assert s.segment_id == "s001"
    assert s.kind == "body"


def test_agent_config_defaults():
    c = AgentConfig(agent_id="test_agent", name="测试")
    assert c.enabled is True
    assert c.kind == "reviewer"
    assert c.priority == 50


def test_selector_result():
    r = SelectorResult(
        detected_article_type="news",
        selected_agents=[AgentSelection(agent_id="fact_checker", reason="需要核查")]
    )
    assert r.status == "success"
    assert len(r.selected_agents) == 1


def test_finding_required_fields():
    f = Finding(
        agent_id="test",
        risk_level="medium",
        confidence="medium",
        issue_type="测试",
        original_quote="原文",
        problem="问题",
        possible_consequence="后果",
        suggestion="建议",
    )
    assert f.original_quote == "原文"


def test_make_finding_id():
    fid = make_finding_id("risk_reviewer", "测试原文摘录", "test_issue")
    assert fid.startswith("f_")
    assert len(fid) == 14  # "f_" + 12 hex chars


def test_make_finding_id_deterministic():
    assert make_finding_id("a", "b", "c") == make_finding_id("a", "b", "c")


def test_make_run_id():
    rid = make_run_id()
    assert len(rid) > 10
    assert "_" in rid


def test_review_run_result():
    r = ReviewRunResult(
        run_id="test_001",
        article=ArticleInput(body="test"),
        final_report={},
    )
    assert r.run_id == "test_001"
