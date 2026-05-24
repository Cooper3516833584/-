"""仲裁分层：将 Finding 分配到四个 bucket 中。"""

from ..schemas import Finding, AgentResult, FinalReport
from .merger import collect_findings, merge_findings
from .scoring import score_finding


def assign_bucket(score: float, finding: Finding) -> str:
    """根据分数和特殊规则分配 bucket。

    特殊强制规则：
    - risk_level=high 且 confidence=medium/high → 至少 should_fix
    - 隐私授权问题且 medium/high → 至少 should_fix
    - 事实错误且 confidence=high → 至少 should_fix
    - 只有 style_guides/examples 的风格建议 → 不能进入 must_fix
    - confidence=low 且无 rules/cases → 不能进入 must_fix
    - format 且 risk_level 非 high → 不能进入 must_fix
    """
    # 先用分数分层
    if finding.confidence == "low" and finding.risk_level != "high":
        bucket = "reference"
    elif score >= 85:
        bucket = "must_fix"
    elif score >= 60:
        bucket = "should_fix"
    elif score >= 35:
        bucket = "optional"
    else:
        bucket = "reference"

    # 向上调整
    if finding.risk_level == "high" and finding.confidence in ("medium", "high"):
        if bucket in ("optional", "reference"):
            bucket = "should_fix"

    tags = set(finding.tags)
    if ("privacy" in tags or "authorization" in tags) and finding.risk_level in ("medium", "high"):
        if bucket in ("optional", "reference"):
            bucket = "should_fix"

    if "fact_error" in tags and finding.confidence == "high":
        if bucket in ("optional", "reference"):
            bucket = "should_fix"

    # 向下调整
    evidence_types = {e.source_type for e in finding.evidence}
    style_only = evidence_types.issubset({"style_guides", "examples", "article"})
    if style_only and bucket == "must_fix":
        bucket = "should_fix"

    if finding.confidence == "low":
        has_strong = evidence_types & {"rules", "cases"}
        if not has_strong and bucket == "must_fix":
            bucket = "should_fix"

    if "format" in tags and finding.risk_level != "high" and bucket == "must_fix":
        bucket = "should_fix"

    return bucket


def build_arbitration_result(
    findings: list[Finding],
) -> dict:
    """对所有 findings 评分、分层、排序，返回分桶结果。"""
    # 评分
    scored = []
    for f in findings:
        src_count = 1
        if hasattr(f, 'metadata') and f.metadata:
            src_count = f.metadata.get("merged_from_count", 1)
        s = score_finding(f, src_count)
        bucket = assign_bucket(s, f)
        scored.append((s, bucket, f))

    # 桶内排序：score 降序 → risk_level → confidence → 原文顺序
    risk_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    conf_order = {"high": 0, "medium": 1, "low": 2}

    def sort_key(item):
        s, bucket, f = item
        return (
            -s,
            risk_order.get(f.risk_level, 99),
            conf_order.get(f.confidence, 99),
        )

    scored.sort(key=sort_key)

    buckets: dict[str, list[Finding]] = {
        "must_fix": [],
        "should_fix": [],
        "optional": [],
        "reference": [],
    }

    for s, bucket, f in scored:
        buckets[bucket].append(f)

    return {
        "buckets": buckets,
        "scores": {f.finding_id or str(i): s for i, (s, _, f) in enumerate(scored)},
    }


def calculate_overall_risk(must_count: int, should_count: int,
                           optional_count: int) -> str:
    """根据各 bucket 数量计算总体风险等级。"""
    if must_count >= 1:
        return "high"
    if should_count >= 2:
        return "medium"
    if should_count == 1 or optional_count >= 3:
        return "low"
    return "info"
