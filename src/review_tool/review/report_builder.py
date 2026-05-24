"""审稿报告构造器。"""

from ..schemas import (
    ArticleInput, ArticleSegment, SelectorResult, AgentResult,
    KnowledgeChunk, Finding, FinalReport, ReviewRunResult,
)
from .merger import collect_findings, merge_findings
from .arbitrator import build_arbitration_result, calculate_overall_risk
from .validator import validate_agent_results


def build_final_report(
    article: ArticleInput,
    selector_result: SelectorResult,
    selected_agent_ids: list[str],
    retrieved_context: list[KnowledgeChunk],
    agent_results: list[AgentResult],
    warnings: list[str],
    errors: list[dict],
) -> tuple[dict, list[Finding]]:
    """构建最终审稿报告。

    Returns:
        (final_report_dict, merged_findings) 元组。
    """
    validated = validate_agent_results(agent_results)
    findings = collect_findings(validated)
    merged = merge_findings(findings)

    arb_result = build_arbitration_result(merged)
    buckets = arb_result["buckets"]

    must_count = len(buckets["must_fix"])
    should_count = len(buckets["should_fix"])
    optional_count = len(buckets["optional"])
    reference_count = len(buckets["reference"])
    overall = calculate_overall_risk(must_count, should_count, optional_count)

    # 收集 agent 执行明细
    agent_execution = []
    for r in validated:
        agent_execution.append({
            "agent_id": r.agent_id,
            "agent_name": r.agent_name,
            "status": r.status,
            "findings_count": len(r.findings),
            "summary": r.summary,
            "error": r.error_message,
            "latency_ms": r.latency_ms,
            "token_usage": r.token_usage,
        })

    # 知识库使用摘要
    knowledge_used = []
    seen_docs = set()
    for c in retrieved_context:
        if c.doc_id not in seen_docs:
            seen_docs.add(c.doc_id)
            knowledge_used.append({
                "doc_id": c.doc_id,
                "title": c.title,
                "source_type": c.source_type,
            })

    # 将 findings 转为可序列化的 dict
    def finding_to_dict(f: Finding) -> dict:
        return {
            "finding_id": f.finding_id,
            "agent_id": f.agent_id,
            "agent_name": f.agent_name,
            "risk_level": f.risk_level,
            "confidence": f.confidence,
            "issue_type": f.issue_type,
            "original_quote": f.original_quote,
            "segment_id": f.segment_id,
            "problem": f.problem,
            "possible_consequence": f.possible_consequence,
            "suggestion": f.suggestion,
            "evidence": [e.model_dump() for e in f.evidence],
            "tags": f.tags,
            "requires_attention": f.requires_attention,
            "metadata": f.metadata,
        }

    report = {
        "summary": {
            "total_findings": len(merged),
            "must_fix_count": must_count,
            "should_fix_count": should_count,
            "optional_count": optional_count,
            "reference_count": reference_count,
            "overall_risk_level": overall,
            "critical_warnings": [w for w in warnings if "失败" in w or "错误" in w],
        },
        "selector": {
            "status": selector_result.status,
            "detected_article_type": selector_result.detected_article_type,
            "detected_tags": selector_result.detected_tags,
            "selected_agents": [s.model_dump() for s in selector_result.selected_agents],
            "reasoning_summary": selector_result.reasoning_summary,
            "final_selected_agent_ids": selected_agent_ids,
        },
        "buckets": {
            "must_fix": [finding_to_dict(f) for f in buckets["must_fix"]],
            "should_fix": [finding_to_dict(f) for f in buckets["should_fix"]],
            "optional": [finding_to_dict(f) for f in buckets["optional"]],
            "reference": [finding_to_dict(f) for f in buckets["reference"]],
        },
        "agent_execution": agent_execution,
        "knowledge_used": knowledge_used,
        "warnings": warnings,
        "errors": errors,
    }

    return report, merged
