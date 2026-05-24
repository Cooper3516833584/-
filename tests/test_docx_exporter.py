"""DOCX 导出器测试。"""

from pathlib import Path

from docx import Document

from review_tool.exporters.docx_exporter import export_docx
from review_tool.schemas import ArticleInput, ReviewRunResult


def test_export_docx_creates_file(tmp_path: Path):
    result = ReviewRunResult(
        run_id="test_run",
        article=ArticleInput(title="测试", body="正文"),
        selected_agent_ids=["fact_checker"],
        final_report={
            "summary": {
                "overall_risk_level": "info",
                "must_fix_count": 0,
                "should_fix_count": 0,
                "optional_count": 0,
                "reference_count": 0,
            },
            "selector": {
                "detected_article_type": "news",
                "detected_tags": [],
                "reasoning_summary": "测试",
            },
            "buckets": {
                "must_fix": [],
                "should_fix": [],
                "optional": [],
                "reference": [],
            },
            "agent_execution": [],
            "knowledge_used": [],
            "warnings": [],
            "errors": [],
        },
    )

    out = tmp_path / "report.docx"
    export_docx(result, out)

    assert out.exists()
    doc = Document(out)
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "智能审稿报告" in text
    assert "审稿总览" in text
