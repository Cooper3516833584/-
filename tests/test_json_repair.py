"""JSON 提取测试。"""

from review_tool.llm.json_repair import extract_json_text, JSONParseError


def test_extract_plain_json_object():
    text = '{"key": "value"}'
    result = extract_json_text(text)
    assert '"key"' in result


def test_extract_from_markdown_codeblock():
    text = '```json\n{"key": "value"}\n```'
    result = extract_json_text(text)
    assert '"key"' in result


def test_extract_from_text_with_surrounding():
    text = '一些文字 {"key": "value"} 后面文字'
    result = extract_json_text(text)
    assert '"key"' in result


def test_extract_invalid_raises():
    try:
        extract_json_text("这只是一段话，没有 JSON")
        assert False
    except JSONParseError:
        pass
