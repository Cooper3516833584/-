"""Markdown 审稿报告导出。"""

from pathlib import Path
from ..schemas import ReviewRunResult

_BUCKET_LABELS = {
    "must_fix": "三、必须修改",
    "should_fix": "四、建议修改",
    "optional": "五、可选优化",
    "reference": "六、仅供参考",
}

_RISK_LABELS = {"high": "高", "medium": "中", "low": "低", "info": "信息"}
_CONF_LABELS = {"high": "高", "medium": "中", "low": "低"}


def export_markdown(result: ReviewRunResult, output_path: Path) -> None:
    """将审稿结果导出为 Markdown 报告文件。"""
    report = result.final_report
    summary = report.get("summary", {})
    selector = report.get("selector", {})
    buckets = report.get("buckets", {})
    agent_exec = report.get("agent_execution", [])
    knowledge = report.get("knowledge_used", [])
    warnings = report.get("warnings", [])
    errors = report.get("errors", [])

    lines: list[str] = []

    # 标题
    lines.append("# 智能审稿报告")
    lines.append("")

    # 一、审稿总览
    lines.append("## 一、审稿总览")
    lines.append("")
    lines.append(f"- 总体风险等级：**{_label(summary.get('overall_risk_level', 'unknown'))}**")
    lines.append(f"- 必须修改：{summary.get('must_fix_count', 0)} 条")
    lines.append(f"- 建议修改：{summary.get('should_fix_count', 0)} 条")
    lines.append(f"- 可选优化：{summary.get('optional_count', 0)} 条")
    lines.append(f"- 仅供参考：{summary.get('reference_count', 0)} 条")
    lines.append(f"- 启用 Agent：{', '.join(result.selected_agent_ids) if result.selected_agent_ids else '无'}")
    lines.append("")

    # 二、Selector Agent 判断
    lines.append("## 二、Selector Agent 判断")
    lines.append("")
    lines.append(f"- 判断稿件类型：{selector.get('detected_article_type', 'unknown')}")
    lines.append(f"- 识别标签：{', '.join(selector.get('detected_tags', [])) or '无'}")
    lines.append(f"- 选择理由摘要：{selector.get('reasoning_summary', '无')}")
    lines.append("")

    # 三～六、各 bucket
    for bucket_key in ["must_fix", "should_fix", "optional", "reference"]:
        items = buckets.get(bucket_key, [])
        lines.append(f"## {_BUCKET_LABELS[bucket_key]}")
        lines.append("")

        if not items:
            lines.append("无")
            lines.append("")
            continue

        for i, item in enumerate(items, 1):
            lines.append(f"### {i}. {item.get('issue_type', '未分类')}")
            lines.append("")
            lines.append(f"- **风险等级**：{_RISK_LABELS.get(item.get('risk_level', 'info'), item.get('risk_level', ''))}")
            lines.append(f"- **置信度**：{_CONF_LABELS.get(item.get('confidence', 'low'), item.get('confidence', ''))}")
            lines.append(f"- **来源 Agent**：{item.get('agent_name', item.get('agent_id', ''))}")
            lines.append(f"- **原文摘录**：{item.get('original_quote', '')}")
            lines.append(f"- **问题**：{item.get('problem', '')}")
            lines.append(f"- **可能后果**：{item.get('possible_consequence', '')}")
            lines.append(f"- **修改建议**：{item.get('suggestion', '')}")

            evidence = item.get('evidence', [])
            if evidence:
                lines.append(f"- **依据**：")
                for ev in evidence:
                    src = ev.get('source_type', '')
                    q = ev.get('quote', '')
                    lines.append(f"  - [{src}] {q}")

            lines.append("")

    # 七、Agent 执行明细
    lines.append("## 七、Agent 执行明细")
    lines.append("")
    if agent_exec:
        for ae in agent_exec:
            status_icon = "OK" if ae.get("status") == "success" else "FAIL"
            lines.append(
                f"- [{status_icon}] **{ae.get('agent_name', ae.get('agent_id', ''))}** "
                f"({ae.get('agent_id', '')}) — "
                f"状态: {ae.get('status', '')}, "
                f"发现问题: {ae.get('findings_count', 0)} 条"
            )
            if ae.get("error"):
                lines.append(f"  - 错误: {ae['error']}")
    else:
        lines.append("无 Agent 执行记录。")
    lines.append("")

    # 八、知识库引用摘要
    lines.append("## 八、知识库引用摘要")
    lines.append("")
    if knowledge:
        for k in knowledge:
            lines.append(f"- [{k.get('source_type', '')}] {k.get('title', '')} ({k.get('doc_id', '')})")
    else:
        lines.append("本次未使用本地知识库材料。")
    lines.append("")

    # 警告和错误
    if warnings:
        lines.append("## 九、警告")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    if errors:
        lines.append("## 十、错误")
        lines.append("")
        for e in errors:
            lines.append(f"- [{e.get('stage', '')}] {e.get('message', '')}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _label(text: str) -> str:
    labels = {"high": "高", "medium": "中", "low": "低", "info": "信息"}
    return labels.get(text, text)
