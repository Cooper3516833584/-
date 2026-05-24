"""通用 txt 文件加载器。"""

from pathlib import Path
from .frontmatter import load_txt_with_frontmatter


def load_all_txt_files(directory: Path, recursive: bool = False) -> list[tuple[Path, dict, str]]:
    """加载目录下所有 txt 文件，返回 (path, metadata, body) 列表。

    Args:
        directory: 要扫描的目录。
        recursive: 是否递归扫描子目录。

    Returns:
        list of (Path, metadata_dict, body_text)
    """
    if not directory.exists():
        return []

    pattern = "**/*.txt" if recursive else "*.txt"
    results = []
    for file_path in sorted(directory.glob(pattern)):
        if not file_path.is_file():
            continue
        try:
            metadata, body = load_txt_with_frontmatter(file_path)
            results.append((file_path, metadata, body))
        except Exception:
            continue

    return results
