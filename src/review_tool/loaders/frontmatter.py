"""YAML front matter 解析器。"""

from pathlib import Path
import yaml


def parse_frontmatter_text(text: str) -> tuple[dict, str]:
    """解析带 YAML front matter 的文本。

    Args:
        text: 完整文本内容。

    Returns:
        (metadata_dict, body_text) 元组。

    Raises:
        ValueError: YAML 解析失败时。
    """
    text = text.strip()

    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    yaml_str = parts[1].strip()
    body = parts[2].strip()

    if not yaml_str:
        return {}, body

    try:
        metadata = yaml.safe_load(yaml_str) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"YAML front matter 解析失败: {e}") from e

    if not isinstance(metadata, dict):
        raise ValueError(f"YAML front matter 必须是字典，实际类型: {type(metadata).__name__}")

    return metadata, body


def load_txt_with_frontmatter(path: Path) -> tuple[dict, str]:
    """从文件路径加载并解析 front matter。"""
    text = path.read_text(encoding="utf-8")
    return parse_frontmatter_text(text)
