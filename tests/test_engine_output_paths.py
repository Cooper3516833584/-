"""审稿输出路径测试。"""

from pathlib import Path

from review_tool.engine import build_review_output_paths
from review_tool.schemas import ArticleInput


def test_build_review_output_paths_uses_article_title(tmp_path: Path):
    article = ArticleInput(title="测试/标题:第一版?", body="正文")

    run_dir, report_docx_path, report_json_path = build_review_output_paths(
        article,
        tmp_path / "output",
        "run_001",
    )

    assert run_dir.name == "测试_标题_第一版_审查结果"
    assert report_docx_path.name == "测试_标题_第一版_审查结果.docx"
    assert report_docx_path.parent == run_dir
    assert report_json_path == run_dir / "report.json"


def test_build_review_output_paths_falls_back_for_blank_title(tmp_path: Path):
    article = ArticleInput(title="", body="正文")

    run_dir, report_docx_path, _ = build_review_output_paths(
        article,
        tmp_path / "output",
        "run_001",
    )

    assert run_dir.name == "未命名稿件_审查结果"
    assert report_docx_path.name == "未命名稿件_审查结果.docx"
