"""统一数据模型定义。所有 Agent 输入输出、知识库、审稿结果均使用这些 Schema。"""

import hashlib
from typing import Literal
from pydantic import BaseModel, Field


# ============================================================
# 基础类型
# ============================================================

ArticleType = Literal[
    "news",
    "commentary",
    "interview",
    "activity",
    "notice",
    "social_post",
    "unknown",
]

RiskLevel = Literal["high", "medium", "low", "info"]
Confidence = Literal["high", "medium", "low"]
AgentKind = Literal["selector", "reviewer", "persona", "arbitrator", "rewriter"]
AgentStatus = Literal["success", "failed", "skipped", "timeout", "invalid_output"]
SourceType = Literal["article", "rules"]
BucketName = Literal["must_fix", "should_fix", "optional", "reference"]


# ============================================================
# 稿件
# ============================================================

class ArticleInput(BaseModel):
    title: str = ""
    body: str
    author: str | None = None
    column: str | None = None
    article_type: ArticleType = "unknown"
    event_background: str | None = None
    images: list[str] = Field(default_factory=list)
    source_path: str | None = None
    metadata: dict = Field(default_factory=dict)


class ArticleSegment(BaseModel):
    segment_id: str
    index: int
    kind: Literal["title", "subtitle", "body", "caption", "summary", "unknown"] = "body"
    text: str
    char_start: int | None = None
    char_end: int | None = None


# ============================================================
# Agent 配置
# ============================================================

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
    kind: AgentKind = "reviewer"
    priority: int = 50
    applies_to: AppliesTo = Field(default_factory=AppliesTo)
    capabilities: list[str] = Field(default_factory=list)
    max_findings: int = 8
    model: ModelConfig = Field(default_factory=ModelConfig)
    output_schema: str = "AgentResult"
    prompt_body: str = ""
    metadata: dict = Field(default_factory=dict)


# ============================================================
# 知识库
# ============================================================

class KnowledgeDocument(BaseModel):
    doc_id: str
    title: str
    source_type: SourceType
    path: str
    tags: list[str] = Field(default_factory=list)
    content: str
    metadata: dict = Field(default_factory=dict)


class KnowledgeChunk(BaseModel):
    chunk_id: str
    doc_id: str
    source_type: str
    title: str
    text: str
    tags: list[str] = Field(default_factory=list)
    score: float = 0.0
    metadata: dict = Field(default_factory=dict)


# ============================================================
# Selector
# ============================================================

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


class SelectorInput(BaseModel):
    article: ArticleInput
    segments: list[ArticleSegment]
    agent_catalog: list[dict]
    deterministic_hints: dict = Field(default_factory=dict)


# ============================================================
# 审稿 Findings
# ============================================================

class EvidenceRef(BaseModel):
    source_type: SourceType
    source_id: str | None = None
    quote: str
    note: str | None = None


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
    metadata: dict = Field(default_factory=dict)


class AgentResult(BaseModel):
    agent_id: str
    agent_name: str
    status: AgentStatus
    findings: list[Finding] = Field(default_factory=list)
    summary: str = ""
    raw_output: str | None = None
    error_message: str | None = None
    token_usage: dict = Field(default_factory=dict)
    latency_ms: int | None = None


# ============================================================
# 检索
# ============================================================

class RetrievalQuery(BaseModel):
    query_text: str
    tags: list[str] = Field(default_factory=list)
    preferred_sources: list[str] = Field(default_factory=list)


# ============================================================
# 报告
# ============================================================

class ReviewError(BaseModel):
    stage: str
    error_type: str
    message: str
    detail: dict = Field(default_factory=dict)


class FinalReport(BaseModel):
    summary: dict = Field(default_factory=dict)
    selector: dict = Field(default_factory=dict)
    buckets: dict[str, list[dict]] = Field(default_factory=dict)
    agent_execution: list[dict] = Field(default_factory=list)
    knowledge_used: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)


class ReviewRunResult(BaseModel):
    run_id: str
    article: ArticleInput
    segments: list[ArticleSegment] = Field(default_factory=list)
    selector_result: SelectorResult = Field(default_factory=SelectorResult)
    selected_agent_ids: list[str] = Field(default_factory=list)
    retrieved_context: list[KnowledgeChunk] = Field(default_factory=list)
    agent_results: list[AgentResult] = Field(default_factory=list)
    merged_findings: list[Finding] = Field(default_factory=list)
    final_report: dict = Field(default_factory=dict)
    errors: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ============================================================
# 工具函数
# ============================================================

def make_finding_id(agent_id: str, original_quote: str, issue_type: str) -> str:
    raw = f"{agent_id}|{issue_type}|{original_quote}".encode("utf-8")
    return "f_" + hashlib.sha1(raw).hexdigest()[:12]


def make_run_id() -> str:
    from datetime import datetime
    import secrets

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(3)
    return f"{ts}_{suffix}"
