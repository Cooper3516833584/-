"""评分与仲裁测试。"""

from review_tool.schemas import Finding, EvidenceRef
from review_tool.review.scoring import score_finding
from review_tool.review.arbitrator import assign_bucket, calculate_overall_risk
from review_tool.review.merger import merge_findings


def _make_finding(risk="medium", conf="medium", tags=None, evidence=None):
    return Finding(
        agent_id="test",
        risk_level=risk,
        confidence=conf,
        issue_type="test_issue",
        original_quote="原文摘录",
        problem="问题描述",
        possible_consequence="后果",
        suggestion="建议",
        tags=tags or [],
        evidence=evidence or [],
    )


def test_score_rules_evidence_higher():
    f1 = _make_finding(evidence=[EvidenceRef(source_type="rules", quote="规则引用")])
    f2 = _make_finding(evidence=[EvidenceRef(source_type="examples", quote="范例引用")])
    assert score_finding(f1, 1) > score_finding(f2, 1)


def test_score_single_agent():
    f = _make_finding()
    s = score_finding(f, 1)
    assert 0 <= s <= 120


def test_assign_bucket_must_fix():
    f = _make_finding(risk="high", conf="high", evidence=[
        EvidenceRef(source_type="rules", quote="必须这样做")
    ])
    bucket = assign_bucket(score_finding(f, 2), f)
    assert bucket == "must_fix"


def test_low_confidence_not_must_fix():
    f = _make_finding(risk="medium", conf="low")
    bucket = assign_bucket(score_finding(f, 1), f)
    assert bucket in ("reference", "optional")


def test_merge_findings_deduplicate():
    f1 = _make_finding()
    f2 = _make_finding()  # 相同 original_quote + issue_type
    merged = merge_findings([f1, f2])
    assert len(merged) == 1


def test_calculate_overall_risk():
    assert calculate_overall_risk(1, 0, 0) == "high"
    assert calculate_overall_risk(0, 2, 0) == "medium"
    assert calculate_overall_risk(0, 1, 0) == "low"
    assert calculate_overall_risk(0, 0, 3) == "low"
    assert calculate_overall_risk(0, 0, 0) == "info"
