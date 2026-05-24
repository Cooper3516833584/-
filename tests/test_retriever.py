"""知识检索器测试。"""

from review_tool.schemas import KnowledgeChunk, AgentConfig
from review_tool.knowledge.retriever import (
    KnowledgeRetriever, filter_context_for_agent,
)


def _make_chunk(doc_id: str, source_type: str, text: str, tags=None):
    return KnowledgeChunk(
        chunk_id=f"{doc_id}::chunk_000",
        doc_id=doc_id,
        source_type=source_type,
        title=doc_id,
        text=text,
        tags=tags or [],
    )


def test_retrieve_empty():
    r = KnowledgeRetriever([])
    assert r.retrieve("test") == []


def test_retrieve_by_keyword():
    chunks = [
        _make_chunk("doc1", "rules", "学生个人信息应脱敏处理"),
        _make_chunk("doc2", "rules", "活动报道应注意照片授权"),
    ]
    r = KnowledgeRetriever(chunks)
    results = r.retrieve("个人信息 隐私", top_k=5)
    assert len(results) > 0
    assert results[0].doc_id == "doc1"


def test_retrieve_with_rules_source_weight():
    chunks = [
        _make_chunk("doc1", "rules", "个人信息保护"),
        _make_chunk("doc2", "rules", "活动照片授权规范"),
    ]
    r = KnowledgeRetriever(chunks)
    results = r.retrieve("个人信息", top_k=5)
    assert results
    assert results[0].source_type == "rules"


def test_filter_context_for_agent_limits_context():
    chunks = [
        _make_chunk("d1", "rules", "规则1"),
        _make_chunk("d2", "article", "原文证据"),
    ]
    agent = AgentConfig(
        agent_id="test",
        name="test",
    )
    filtered = filter_context_for_agent(chunks, agent, max_chunks=1)
    assert len(filtered) == 1
    assert filtered[0].doc_id == "d1"
