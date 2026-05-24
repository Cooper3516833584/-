"""从 LLM 输出中提取 JSON 文本。"""

import json
import re


class JSONParseError(Exception):
    """JSON 解析失败。"""
    pass


def extract_json_text(text: str) -> str:
    """从 LLM 输出中提取最可能的 JSON 字符串。

    Args:
        text: LLM 原始输出。

    Returns:
        提取的 JSON 字符串。

    Raises:
        JSONParseError: 无法提取 JSON 时。
    """
    text = text.strip()

    # 尝试直接解析
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # 提取 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        candidate = m.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 找到第一个 { 或 [ 到最后一个 } 或 ]
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = text.find(start_char)
        end_idx = text.rfind(end_char)
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate = text[start_idx:end_idx + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue

    raise JSONParseError(f"无法从输出中提取合法 JSON。输出前 200 字符: {text[:200]}")
