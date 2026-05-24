"""风险评分。"""

from ..schemas import Finding

RISK_LEVEL_SCORE = {
    "high": 90,
    "medium": 60,
    "low": 30,
    "info": 10,
}

CONFIDENCE_MULTIPLIER = {
    "high": 1.0,
    "medium": 0.75,
    "low": 0.45,
}


def score_finding(f: Finding, source_agent_count: int = 1) -> float:
    """计算单条 Finding 的综合风险分数。

    Args:
        f: Finding 对象。
        source_agent_count: 来源 Agent 数量（合并后 ≥ 1）。

    Returns:
        0-120 区间的分数。
    """
    base = RISK_LEVEL_SCORE.get(f.risk_level, 10)
    score = base * CONFIDENCE_MULTIPLIER.get(f.confidence, 0.45)

    source_types = {e.source_type for e in f.evidence}

    if "article" in source_types:
        score += 5
    if "rules" in source_types:
        score += 10
    if "cases" in source_types:
        score += 8
    if "risky_phrases" in source_types:
        score += 5

    # 多 Agent 命中加分
    score += min(max(source_agent_count - 1, 0) * 6, 18)

    tags = set(f.tags)
    if "privacy" in tags or "authorization" in tags:
        score += 10
    if "fact_error" in tags:
        score += 6
    if "format" in tags:
        score -= 10

    return max(score, 0.0)
