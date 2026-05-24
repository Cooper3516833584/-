"""Front matter 解析测试。"""

import tempfile
from pathlib import Path
from review_tool.loaders.frontmatter import parse_frontmatter_text, load_txt_with_frontmatter


def test_parse_no_frontmatter():
    meta, body = parse_frontmatter_text("这是正文")
    assert meta == {}
    assert body == "这是正文"


def test_parse_with_frontmatter():
    text = "---\ntitle: 测试\n---\n这是正文"
    meta, body = parse_frontmatter_text(text)
    assert meta == {"title": "测试"}
    assert body == "这是正文"


def test_parse_empty_frontmatter():
    text = "---\n---\n正文"
    meta, body = parse_frontmatter_text(text)
    assert meta == {}
    assert body == "正文"


def test_parse_list_in_frontmatter():
    text = "---\ntags:\n  - a\n  - b\n---\n正文"
    meta, body = parse_frontmatter_text(text)
    assert meta == {"tags": ["a", "b"]}
    assert body == "正文"


def test_parse_non_dict_frontmatter():
    text = "---\n- item1\n- item2\n---\n正文"
    try:
        parse_frontmatter_text(text)
        assert False, "应该抛出 ValueError"
    except ValueError:
        pass


def test_load_txt_with_frontmatter():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("---\nkey: value\n---\n正文内容")
        tmp = Path(f.name)

    try:
        meta, body = load_txt_with_frontmatter(tmp)
        assert meta == {"key": "value"}
        assert body == "正文内容"
    finally:
        tmp.unlink()
