# 03 数据结构与 Schema

## 1. 为什么先定 Schema

这个项目的关键不是先写漂亮 Prompt，而是先固定数据结构。因为所有 Agent 都要被统一执行、校验、合并和仲裁。

如果没有统一 Schema，会出现：

```text
Agent A 输出“问题/建议”
Agent B 输出“风险/修改方案”
Agent C 输出一段自然语言
仲裁器无法稳定合并
报告生成器无法稳定输出
```

因此第一版必须先实现 `schemas.py`。

## 2. ArticleInput

```python
from pydantic import BaseModel, Field
from typing import Literal

ArticleType = Literal[
    "news",
    "commentary",
    "interview",
    "activity",
    "notice",
    "social_post",
    "unknown",
]

class ArticleInput(BaseModel):
    title: str = ""
    body: str
    author: str | None = None
    column: str | None = None
    article_type: ArticleType = "unknown"
    images: list[str] = Field(default_factory=list)
    source_path: str | None = None
    metadata: dict = Field(default_factory=dict)
```

字段要求：

```text
title 可以为空，但 preprocess 阶段要尽量从正文提取。
body 不允许为空。
article_type 初始可以 unknown，由 Selector Agent 判断。
images 第一版可以只记录文件名，不处理图片内容。
metadata 存储 front matter 中未被识别的其它字段。
```

## 3. ArticleSegment

```python
class ArticleSegment(BaseModel):
    segment_id: str
    index: int
    kind: Literal["title", "subtitle", "body", "caption", "summary", "unknown"] = "body"
    text: str
    char_start: int | None = None
    char_end: int | None = None
```

实现要求：

```text
segment_id 使用 s001、s002 这样的稳定编号。
标题单独作为 title segment。
正文按自然段切分。
空段落跳过。
```

## 4. AgentConfig

```python
class ModelConfig(BaseModel):
    name: str = "default"
    temperature: float = 0.2
    timeout_seconds: int = 90
    max_retries: int = 2

class AppliesTo(BaseModel):
    article_types: list[str] = Field(default_factory=lambda: ["*"])
    columns: list[str] = Field(default_factory=lambda: ["*"])
    tags: list[str] = Field(default_factory=list)

class AgentConfig(BaseModel):
    agent_id: str
    name: str
    enabled: bool = True
    kind: Literal["selector", "reviewer", "arbitrator", "rewriter"] = "reviewer"
    priority: int = 50
    applies_to: AppliesTo = Field(default_factory=AppliesTo)
    capabilities: list[str] = Field(default_factory=list)
    knowledge_sources: list[str] = Field(default_factory=list)
    max_findings: int = 8
    model: ModelConfig = Field(default_factory=ModelConfig)
    output_schema: str = "AgentResult"
    prompt_body: str = ""
    metadata: dict = Field(default_factory=dict)
```

注意：

```text
prompt_body 来自 txt 文件 front matter 后面的正文。
Selector Agent 的 kind 必须为 selector。
普通审稿 Agent 的 kind 必须为 reviewer。
```

## 5. KnowledgeDocument

```python
class KnowledgeDocument(BaseModel):
    doc_id: str
    title: str
    source_type: Literal["cases", "rules", "style_guides", "risky_phrases", "examples"]
    path: str
    tags: list[str] = Field(default_factory=list)
    content: str
    metadata: dict = Field(default_factory=dict)
```

## 6. KnowledgeChunk

```python
class KnowledgeChunk(BaseModel):
    chunk_id: str
    doc_id: str
    source_type: str
    title: str
    text: str
    tags: list[str] = Field(default_factory=list)
    score: float = 0.0
    metadata: dict = Field(default_factory=dict)
```

切块规则：

```text
优先按标题和空行切。
每块建议 500 到 1200 中文字。
过短块可合并。
保留 doc_id、source_type、title、tags。
```

## 7. SelectorResult

Selector Agent 输出必须符合：

```python
class AgentSelection(BaseModel):
    agent_id: str
    reason: str
    priority: int = 50

class SelectorResult(BaseModel):
    status: Literal["success", "failed"] = "success"
    detected_article_type: ArticleType = "unknown"
    detected_tags: list[str] = Field(default_factory=list)
    selected_agents: list[AgentSelection] = Field(default_factory=list)
    context_queries: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    warnings: list[str] = Field(default_factory=list)
```

字段说明：

```text
detected_article_type：Selector 对稿件类型的判断。
detected_tags：例如 privacy, title_risk, interview, group_conflict, event_report。
selected_agents：要启用的 Agent。
context_queries：给知识库检索器使用的查询词。
reasoning_summary：简短说明，不要输出长篇思考。
warnings：Selector 对自身不确定性的提示。
```

Selector 不应该输出私密链路推理，只输出可读摘要。

## 8. EvidenceRef

```python
RiskLevel = Literal["high", "medium", "low", "info"]
Confidence = Literal["high", "medium", "low"]

class EvidenceRef(BaseModel):
    source_type: Literal["article", "cases", "rules", "style_guides", "risky_phrases", "examples"]
    source_id: str | None = None
    quote: str
    note: str | None = None
```

每条 Finding 至少要包含一个 article 类型的 evidence。

## 9. Finding

```python
class Finding(BaseModel):
    finding_id: str | None = None
    agent_id: str
    agent_name: str | None = None

    risk_level: RiskLevel
    confidence: Confidence
    issue_type: str

    original_quote: str
    segment_id: str | None = None

    problem: str
    possible_consequence: str
    suggestion: str

    evidence: list[EvidenceRef] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    requires_attention: bool = False
```

校验要求：

```text
original_quote 不能为空。
problem 不能为空。
suggestion 不能为空。
possible_consequence 可以短，但不能空。
risk_level 必须是 high/medium/low/info。
confidence 必须是 high/medium/low。
issue_type 必须是非空字符串。
```

## 10. AgentResult

```python
class AgentResult(BaseModel):
    agent_id: str
    agent_name: str
    status: Literal["success", "failed", "skipped", "timeout", "invalid_output"]
    findings: list[Finding] = Field(default_factory=list)
    summary: str = ""
    raw_output: str | None = None
    error_message: str | None = None
    token_usage: dict = Field(default_factory=dict)
    latency_ms: int | None = None
```

## 11. ReviewRunResult

```python
class ReviewRunResult(BaseModel):
    run_id: str
    article: ArticleInput
    segments: list[ArticleSegment]
    selector_result: SelectorResult
    selected_agent_ids: list[str]
    retrieved_context: list[KnowledgeChunk]
    agent_results: list[AgentResult]
    merged_findings: list[Finding]
    final_report: dict
    errors: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

## 12. 生成 finding_id 的规则

Agent 可以不输出 finding_id，由系统补。

推荐实现：

```python
import hashlib

def make_finding_id(agent_id: str, original_quote: str, issue_type: str) -> str:
    raw = f"{agent_id}|{issue_type}|{original_quote}".encode("utf-8")
    return "f_" + hashlib.sha1(raw).hexdigest()[:12]
```

## 13. Schema 文件落地位置

统一放在：

```text
src/review_tool/schemas.py
```

不要分散在多个文件，第一版保持简单。
