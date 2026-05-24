"""稿件加载与预处理。"""

import re
from pathlib import Path
from ..schemas import ArticleInput, ArticleSegment
from ..loaders.frontmatter import load_txt_with_frontmatter

_IMG_PATTERN = re.compile(r"!\[.*?\]\((.+?)\)")


def load_article_file(path: Path) -> ArticleInput:
    """从 Markdown 文件加载稿件。

    支持 YAML front matter（title, author, column, article_type,
    event_background, images）。
    """
    if not path.exists():
        raise FileNotFoundError(f"稿件文件不存在: {path}")

    text = path.read_text(encoding="utf-8")

    try:
        metadata, body = load_txt_with_frontmatter(path)
    except ValueError:
        metadata, body = {}, text

    # 从正文提取图片
    images = list(metadata.get("images", []))
    for m in _IMG_PATTERN.finditer(body):
        img_path = m.group(1)
        if img_path not in images:
            images.append(img_path)

    # 提取标题：优先用 metadata 中的 title，否则从正文第一行 # 标题提取
    title = str(metadata.get("title", ""))
    if not title:
        for line in body.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                break

    article_type = str(metadata.get("article_type", "unknown"))
    event_background = _optional_str(
        metadata.get("event_background")
        or metadata.get("事件背景")
        or metadata.get("background")
    )

    return ArticleInput(
        title=title,
        body=body,
        author=metadata.get("author"),
        column=metadata.get("column"),
        article_type=article_type,  # type: ignore[arg-type]
        event_background=event_background,
        images=images,
        source_path=str(path.resolve()),
        metadata={k: v for k, v in metadata.items()
                  if k not in {
                      "title", "author", "column", "article_type",
                      "event_background", "事件背景", "background", "images",
                  }},
    )


def _optional_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def preprocess_article(article: ArticleInput) -> list[ArticleSegment]:
    """将稿件切分为段落片段。

    规则：
    - 第一行 # 标题作为 title segment
    - 后续 ## 作为 subtitle segment
    - 正文段落作为 body segment
    - 空行跳过
    - segment_id 使用 s001, s002 稳定编号
    """
    segments: list[ArticleSegment] = []
    lines = article.body.split("\n")
    idx = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("# "):
            kind = "title" if idx == 0 else "subtitle"
            segments.append(ArticleSegment(
                segment_id=f"s{len(segments) + 1:03d}",
                index=len(segments),
                kind=kind,  # type: ignore[arg-type]
                text=stripped.lstrip("# ").strip(),
            ))
        elif stripped.startswith("## "):
            segments.append(ArticleSegment(
                segment_id=f"s{len(segments) + 1:03d}",
                index=len(segments),
                kind="subtitle",
                text=stripped[3:].strip(),
            ))
        elif stripped.startswith("!["):
            # 图片标注行，记录为 caption
            segments.append(ArticleSegment(
                segment_id=f"s{len(segments) + 1:03d}",
                index=len(segments),
                kind="caption",
                text=stripped,
            ))
        else:
            segments.append(ArticleSegment(
                segment_id=f"s{len(segments) + 1:03d}",
                index=len(segments),
                kind="body",
                text=stripped,
                char_start=article.body.find(stripped) if stripped else None,
                char_end=article.body.find(stripped) + len(stripped) if stripped else None,
            ))
        idx += 1

    return segments
