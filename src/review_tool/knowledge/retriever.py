"""知识检索器：关键词匹配 + 简易打分 + 来源加权。"""

import re
from ..schemas import KnowledgeChunk, AgentConfig


class KnowledgeRetriever:
    """基于关键词匹配和来源加权的简易检索器。"""

    def __init__(self, chunks: list[KnowledgeChunk]):
        self._chunks = chunks

    def retrieve(
        self,
        query: str,
        tags: list[str] | None = None,
        preferred_sources: list[str] | None = None,
        top_k: int = 12,
    ) -> list[KnowledgeChunk]:
        """检索最相关的知识块。

        Args:
            query: 查询文本。
            tags: 要匹配的标签。
            preferred_sources: 优先来源列表。
            top_k: 返回数量上限。

        Returns:
            按分数降序排列的知识块列表。
        """
        if not self._chunks:
            return []

        query_terms = _extract_query_terms(query)
        if tags:
            query_terms.extend(tags)

        preferred = preferred_sources or []

        scored: list[KnowledgeChunk] = []
        for c in self._chunks:
            score = _score_chunk(c, query_terms, preferred)
            if score > 0:
                c_copy = c.model_copy()
                c_copy.score = score
                scored.append(c_copy)

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)


def _extract_query_terms(query: str) -> list[str]:
    """从查询文本中提取关键词（按空格和标点切分，去重，去空）。"""
    terms = re.split(r"[，。、；：；！？\s,.;:!?\n]+", query)
    return [t.strip().lower() for t in terms if len(t.strip()) >= 2]


def _score_chunk(
    chunk: KnowledgeChunk,
    query_terms: list[str],
    preferred_sources: list[str],
) -> float:
    """对单个 chunk 打分。"""
    score = 0.0
    text = (chunk.title + "\n" + chunk.text).lower()

    for term in query_terms:
        if term and term in text:
            score += 2.0

    for tag in chunk.tags:
        if tag.lower() in [t.lower() for t in query_terms]:
            score += 1.5

    if chunk.source_type in preferred_sources:
        score += 1.0

    # 来源权重加成
    source_weights = {
        "rules": 0.8,
        "cases": 0.7,
        "risky_phrases": 0.5,
        "style_guides": 0.3,
        "examples": 0.2,
    }
    score += source_weights.get(chunk.source_type, 0.0)

    return score


def filter_context_for_agent(
    chunks: list[KnowledgeChunk],
    agent: AgentConfig,
    max_chunks: int = 8,
) -> list[KnowledgeChunk]:
    """根据 Agent 的 knowledge_sources 过滤上下文。"""
    sources = set(agent.knowledge_sources or [])
    if not sources:
        return chunks[:max_chunks]
    filtered = [c for c in chunks if c.source_type in sources]
    return filtered[:max_chunks]
