"""知识文档切块器。"""

import re
from ..schemas import KnowledgeDocument, KnowledgeChunk

# 粗略估算中文字数（包括中文标点）
_CN_CHAR_PAT = re.compile(r"[一-鿿　-〿＀-￯]")


def _count_cn_chars(text: str) -> int:
    return len(_CN_CHAR_PAT.findall(text))


def chunk_documents(docs: list[KnowledgeDocument]) -> list[KnowledgeChunk]:
    """将文档列表切分为 KnowledgeChunk 列表。

    策略：
    1. 先按 Markdown 标题切分。
    2. 标题块太长则按空行切分。
    3. 每块控制在 500-1200 中文字。
    4. 少于 120 字的块与相邻块合并。
    """
    chunks: list[KnowledgeChunk] = []

    for doc in docs:
        doc_chunks = _chunk_one_document(doc)
        chunks.extend(doc_chunks)

    # 合并过短块
    chunks = _merge_short_chunks(chunks)

    # 重新编号
    for i, c in enumerate(chunks):
        c.metadata["chunk_index"] = i

    return chunks


def _chunk_one_document(doc: KnowledgeDocument) -> list[KnowledgeChunk]:
    """对单个文档切块。"""
    content = doc.content
    if not content.strip():
        return []

    # 按 ## 标题切分
    sections = re.split(r"\n(?=##?\s)", content)
    raw_chunks: list[str] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        cn_count = _count_cn_chars(section)
        if cn_count <= 1200:
            raw_chunks.append(section)
        else:
            # 太长则按空行再切
            paragraphs = re.split(r"\n\s*\n", section)
            current = ""
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                if _count_cn_chars(current + "\n\n" + para) <= 1200:
                    current = current + "\n\n" + para if current else para
                else:
                    if current:
                        raw_chunks.append(current)
                    current = para
            if current:
                raw_chunks.append(current)

    chunks = []
    for i, text in enumerate(raw_chunks):
        chunk_id = f"{doc.doc_id}::chunk_{i:03d}"
        chunks.append(KnowledgeChunk(
            chunk_id=chunk_id,
            doc_id=doc.doc_id,
            source_type=doc.source_type,
            title=doc.title,
            text=text,
            tags=list(doc.tags),
            metadata=dict(doc.metadata),
        ))

    return chunks


def _merge_short_chunks(chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
    """合并过短块（< 120 中文字）。"""
    if len(chunks) <= 1:
        return chunks

    merged: list[KnowledgeChunk] = []
    buffer: KnowledgeChunk | None = None

    for c in chunks:
        cn = _count_cn_chars(c.text)
        if cn < 120 and merged:
            # 合并到前一个块
            prev = merged[-1]
            prev.text = prev.text + "\n\n" + c.text
        elif cn < 120 and buffer is None:
            buffer = c
        else:
            if buffer is not None:
                c.text = buffer.text + "\n\n" + c.text
                buffer = None
            merged.append(c)

    if buffer is not None and merged:
        merged[-1].text = merged[-1].text + "\n\n" + buffer.text
    elif buffer is not None:
        merged.append(buffer)

    return merged
