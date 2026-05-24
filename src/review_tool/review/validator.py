"""Agent 输出校验与清洗。"""

from ..schemas import AgentResult, Finding


def validate_agent_results(results: list[AgentResult]) -> list[AgentResult]:
    """校验和清洗所有 Agent 输出。

    对每个 AgentResult：
    - 删除严重缺字段的 finding
    - 清洗 original_quote
    - 修正非法 risk_level/confidence
    """
    for result in results:
        if result.status != "success":
            continue

        cleaned: list[Finding] = []
        for f in result.findings:
            # 清洗 original_quote
            f.original_quote = (f.original_quote or "").strip()

            # 缺少核心字段则丢弃
            if not f.original_quote or not f.problem or not f.suggestion:
                continue

            # 修正非法 risk_level
            if f.risk_level not in ("high", "medium", "low", "info"):
                f.risk_level = "info"

            # 修正非法 confidence
            if f.confidence not in ("high", "medium", "low"):
                f.confidence = "medium"

            cleaned.append(f)

        result.findings = cleaned

    return results
