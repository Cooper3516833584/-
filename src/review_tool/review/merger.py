"""Finding 收集与去重合并。"""

from difflib import SequenceMatcher
from ..schemas import AgentResult, Finding, EvidenceRef


def text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def collect_findings(agent_results: list[AgentResult]) -> list[Finding]:
    """从所有成功的 AgentResult 中收集 findings。"""
    findings: list[Finding] = []
    for result in agent_results:
        if result.status == "success":
            findings.extend(result.findings)
    return findings


def merge_findings(findings: list[Finding]) -> list[Finding]:
    """合并重复和近似的 Finding。

    去重规则：
    1. 精确重复：相同 original_quote + issue_type 合并。
    2. 近似重复：original_quote 相似度 > 0.85 且 issue_type 相同或 tags 有交集。
    3. 同 segment_id + 相近 issue_type 合并。

    合并策略：
    - 保留最高 risk_level 和 confidence。
    - 合并所有 evidence（去重）。
    - 保留最长或最具体的 problem/suggestion。
    - 合并 tags（去重）。
    """
    if len(findings) <= 1:
        return findings

    merged: list[Finding] = []
    used: set[int] = set()

    for i, f1 in enumerate(findings):
        if i in used:
            continue

        group = [f1]
        used.add(i)

        for j, f2 in enumerate(findings):
            if j in used:
                continue

            if _should_merge(f1, f2):
                group.append(f2)
                used.add(j)

        merged.append(_merge_group(group))

    return merged


def _should_merge(f1: Finding, f2: Finding) -> bool:
    """判断两个 Finding 是否应该合并。"""
    q1 = f1.original_quote.strip()
    q2 = f2.original_quote.strip()

    # 精确匹配
    if q1 == q2 and f1.issue_type == f2.issue_type:
        return True

    # 近似匹配
    if text_similarity(q1, q2) > 0.85:
        if f1.issue_type == f2.issue_type:
            return True
        if set(f1.tags) & set(f2.tags):
            return True

    # 同段 + 相近 issue_type
    if f1.segment_id and f1.segment_id == f2.segment_id:
        if f1.issue_type == f2.issue_type:
            return True

    return False


def _merge_group(group: list[Finding]) -> Finding:
    """合并一组 Finding 为一条。"""
    if len(group) == 1:
        return group[0]

    base = group[0]

    # 最高风险等级
    risk_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    best_risk = base.risk_level
    best_confidence = base.confidence
    conf_order = {"high": 0, "medium": 1, "low": 2}

    for f in group[1:]:
        if risk_order.get(f.risk_level, 99) < risk_order.get(best_risk, 99):
            best_risk = f.risk_level
        if conf_order.get(f.confidence, 99) < conf_order.get(best_confidence, 99):
            best_confidence = f.confidence

    # 合并 evidence 去重
    all_evidence: list[EvidenceRef] = []
    seen_quotes: set[str] = set()
    for f in group:
        for ev in f.evidence:
            key = f"{ev.source_type}|{ev.quote}"
            if key not in seen_quotes:
                seen_quotes.add(key)
                all_evidence.append(ev)

    # 合并 tags 去重
    all_tags: list[str] = []
    for f in group:
        for t in f.tags:
            if t not in all_tags:
                all_tags.append(t)

    # 取最长的 problem 和 suggestion
    best_problem = max(group, key=lambda f: len(f.problem)).problem
    best_suggestion = max(group, key=lambda f: len(f.suggestion)).suggestion
    best_consequence = max(group, key=lambda f: len(f.possible_consequence)).possible_consequence

    source_agent_ids = list({f.agent_id for f in group})
    source_agent_names = list({f.agent_name for f in group if f.agent_name})

    merged = Finding(
        finding_id=base.finding_id,
        agent_id=", ".join(source_agent_ids),
        agent_name=", ".join(source_agent_names),
        risk_level=best_risk,
        confidence=best_confidence,
        issue_type=base.issue_type,
        original_quote=base.original_quote,
        segment_id=base.segment_id,
        problem=best_problem,
        possible_consequence=best_consequence,
        suggestion=best_suggestion,
        evidence=all_evidence,
        tags=all_tags,
        requires_attention=best_risk == "high" or len(group) >= 3,
    )

    # 在 metadata 中保存合并来源信息
    merged_data = {
        "source_agent_ids": source_agent_ids,
        "source_agent_names": source_agent_names,
        "merged_from_count": len(group),
    }

    return merged
