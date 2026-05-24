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
        _make_chunk("doc2", "cases", "活动报道应注意照片授权"),
    ]
    r = KnowledgeRetriever(chunks)
    results = r.retrieve("个人信息 隐私", top_k=5)
    assert len(results) > 0
    assert results[0].doc_id == "doc1"


def test_retrieve_prefers_rules():
    chunks = [
        _make_chunk("doc1", "examples", "个人信息保护"),
        _make_chunk("doc2", "rules", "个人信息保护规范"),
    ]
    r = KnowledgeRetriever(chunks)
    results = r.retrieve("个人信息", top_k=5)
    # rules 来源有额外权重加成
    assert results[0].source_type == "rules"


def test_filter_context_for_agent():
    chunks = [
        _make_chunk("d1", "rules", "规则1"),
        _make_chunk("d2", "cases", "案例1"),
        _make_chunk("d3", "style_guides", "风格1"),
    ]
    agent = AgentConfig(
        agent_id="test",
        name="test",
        knowledge_sources=["rules", "cases"],
    )
    filtered = filter_context_for_agent(chunks, agent)
    assert len(filtered) == 2
    sources = {c.source_type for c in filtered}
    assert sources == {"rules", "cases"}
