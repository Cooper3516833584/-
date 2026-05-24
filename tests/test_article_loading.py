"""稿件加载测试。"""

from pathlib import Path

from review_tool.review.preprocess import load_article_file


def test_load_article_event_background(tmp_path: Path):
    article_path = tmp_path / "article.md"
    article_path.write_text(
        "---\n"
        "title: 测试稿件\n"
        "event_background: 活动发生在迎新周。\n"
        "---\n\n"
        "# 测试稿件\n\n正文",
        encoding="utf-8",
    )

    article = load_article_file(article_path)

    assert article.event_background == "活动发生在迎新周。"
    assert "event_background" not in article.metadata


def test_load_article_chinese_event_background(tmp_path: Path):
    article_path = tmp_path / "article.md"
    article_path.write_text(
        "---\n"
        "title: 测试稿件\n"
        "事件背景: 活动发生在初雪当天。\n"
        "---\n\n"
        "# 测试稿件\n\n正文",
        encoding="utf-8",
    )

    article = load_article_file(article_path)

    assert article.event_background == "活动发生在初雪当天。"
    assert "事件背景" not in article.metadata
