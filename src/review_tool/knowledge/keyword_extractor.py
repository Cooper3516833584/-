"""检索查询构造器。"""

from ..schemas import ArticleInput, ArticleSegment, SelectorResult, RetrievalQuery


def build_retrieval_query(
    article: ArticleInput,
    segments: list[ArticleSegment],
    selector_result: SelectorResult,
    hints: dict,
) -> RetrievalQuery:
    """构建知识检索查询。

    合并稿件标题、摘要、Selector 查询和建议标签。
    """
    # 稿件背景和前 300 字正文共同作为摘要线索。
    summary = " ".join(
        part for part in [article.event_background or "", article.body[:300]] if part
    )

    parts = [article.title, summary]
    parts.extend(selector_result.context_queries)
    parts.extend(selector_result.detected_tags)

    query_text = " ".join(p for p in parts if p)

    tags = list(selector_result.detected_tags)
    if hints.get("sensitive_keywords_found"):
        for kw in hints["sensitive_keywords_found"]:
            if kw not in tags:
                tags.append(kw)

    return RetrievalQuery(
        query_text=query_text,
        tags=tags,
        preferred_sources=["rules"],
    )
