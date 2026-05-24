# 06 知识库 txt 加载与检索

## 1. 目标

本项目不使用数据库保存知识材料，而是读取项目根目录下多个文件夹中的 txt 文件。

知识材料目录：

```text
cases/
rules/
style_guides/
risky_phrases/
examples/
```

检索目标：

```text
给 Selector 之后的每个审稿 Agent 提供相关上下文。
让审稿意见尽量引用本地规矩、历史案例、风格标准，而不是凭空发挥。
```

## 2. 知识库加载器

文件：

```text
src/review_tool/loaders/corpus_loader.py
```

接口：

```python
def load_corpus(project_root: Path) -> list[KnowledgeDocument]:
    ...
```

需要扫描：

```python
SOURCE_DIRS = {
    "cases": "cases",
    "rules": "rules",
    "style_guides": "style_guides",
    "risky_phrases": "risky_phrases",
    "examples": "examples",
}
```

每个 txt 解析为 `KnowledgeDocument`。

## 3. 文档 ID 规则

优先级：

```text
1. front matter 中的 case_id/rule_id/style_id/phrase_list_id/example_id/doc_id
2. front matter 中的 id
3. 文件名不含扩展名
```

实现函数：

```python
def infer_doc_id(metadata: dict, path: Path) -> str:
    for key in ["doc_id", "case_id", "rule_id", "style_id", "phrase_list_id", "example_id", "id"]:
        if metadata.get(key):
            return str(metadata[key])
    return path.stem
```

## 4. 文档切块

文件：

```text
src/review_tool/knowledge/chunker.py
```

接口：

```python
def chunk_documents(docs: list[KnowledgeDocument]) -> list[KnowledgeChunk]:
    ...
```

切块策略：

```text
1. 先按 Markdown 标题切。
2. 标题块太长则按空行切。
3. 每块控制在 500 到 1200 中文字。
4. 小于 120 字的块尝试与相邻块合并。
5. risky_phrases 可以按条目切，但保留整份说明。
```

chunk_id 规则：

```python
chunk_id = f"{doc.doc_id}::chunk_{index:03d}"
```

## 5. 第一版检索方式

第一版不强制做 embedding。推荐先做：

```text
关键词匹配 + 简易打分 + 来源加权
```

因为你们的知识材料是中文短文本、校内规则、翻车案例，BM25/关键词已经足够跑通。

后续可加 embedding 检索。

## 6. 检索查询构造

文件：

```text
src/review_tool/knowledge/keyword_extractor.py
```

输入：

```text
ArticleInput
ArticleSegment list
SelectorResult
Deterministic hints
```

输出：

```python
class RetrievalQuery(BaseModel):
    query_text: str
    tags: list[str]
    preferred_sources: list[str]
```

构造逻辑：

```text
query_text = 标题 + 稿件摘要 + Selector context_queries + detected_tags
preferred_sources = 所有来源；若某 Agent 运行时请求，则按 Agent knowledge_sources 过滤
```

## 7. 检索打分

简单实现：

```python
def score_chunk(chunk: KnowledgeChunk, query_terms: list[str], preferred_sources: list[str]) -> float:
    score = 0.0

    text = (chunk.title + "\n" + chunk.text).lower()

    for term in query_terms:
        if term and term.lower() in text:
            score += 2.0

    for tag in chunk.tags:
        if tag in query_terms:
            score += 1.5

    if chunk.source_type in preferred_sources:
        score += 1.0

    if chunk.source_type == "rules":
        score += 0.8
    elif chunk.source_type == "cases":
        score += 0.7
    elif chunk.source_type == "risky_phrases":
        score += 0.5

    return score
```

## 8. 检索接口

文件：

```text
src/review_tool/knowledge/retriever.py
```

接口：

```python
class KnowledgeRetriever:
    def __init__(self, chunks: list[KnowledgeChunk]): ...

    def retrieve(
        self,
        query: str,
        tags: list[str] | None = None,
        preferred_sources: list[str] | None = None,
        top_k: int = 12,
    ) -> list[KnowledgeChunk]:
        ...
```

## 9. Agent 级上下文过滤

运行某个 Agent 时，不要把全部检索结果塞进去。根据 Agent 配置过滤：

```python
def filter_context_for_agent(chunks: list[KnowledgeChunk], agent: AgentConfig, max_chunks: int = 8) -> list[KnowledgeChunk]:
    sources = set(agent.knowledge_sources or [])
    if not sources:
        return chunks[:max_chunks]
    filtered = [c for c in chunks if c.source_type in sources]
    return filtered[:max_chunks]
```

## 10. 上下文格式化

给 LLM 的上下文格式建议：

```text
[知识库材料 1]
source_type: cases
source_id: case_2024_privacy_photo
title: 活动照片未打码引发投诉
quote:
……

[知识库材料 2]
source_type: rules
source_id: school_publicity_rules
title: 学校宣传内容规范摘要
quote:
……
```

要求 Agent 引用时使用：

```json
{
  "source_type": "cases",
  "source_id": "case_2024_privacy_photo",
  "quote": "涉及可识别个人形象的照片，应确认授权或使用模糊处理。"
}
```

## 11. 索引缓存

第一版可选，但建议实现。

文件：

```text
src/review_tool/knowledge/index_cache.py
```

缓存路径：

```text
.cache/corpus_index.jsonl
.cache/file_hashes.json
```

逻辑：

```text
计算 cases/rules/style_guides/risky_phrases/examples 下所有 txt 的 sha1。
如果 hash 没变，加载缓存 chunk。
如果 hash 变化，重新加载并切块。
```

## 12. 空知识库处理

如果没有任何知识材料：

```text
retrieved_context = []
warnings 增加：本次未加载到本地知识材料。
审稿继续。
```

Agent prompt 中也要说明：

```text
本次没有检索到本地知识库材料，你只能基于稿件原文提出审稿意见。不得编造校规或历史案例。
```

## 13. 验收测试

必须写：

```text
test_load_corpus_from_all_dirs
test_frontmatter_doc_id_priority
test_chunk_documents_keeps_source_type
test_retrieve_prefers_rules_and_cases
test_filter_context_for_agent
test_empty_corpus_does_not_crash
```
