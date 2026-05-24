"""Prompt 构造器：为 Selector 和各审稿 Agent 构造 system/user 消息。"""

import json
from ..schemas import (
    ArticleInput, ArticleSegment, AgentConfig, KnowledgeChunk, Finding, EvidenceRef,
)

_COMMON_RULES = """你必须输出 JSON。不得输出 Markdown 代码块的前后缀。
不得输出解释性文字。
所有问题必须绑定原文摘录 (original_quote)。
如果没有发现问题，findings 输出空数组 []。
不得编造校规、历史案例、处分结果。"""


def build_reviewer_prompt(
    agent: AgentConfig,
    article: ArticleInput,
    segments: list[ArticleSegment],
    context: list[KnowledgeChunk],
) -> tuple[str, str]:
    """构造审稿 Agent 的 system 和 user 消息。

    Returns:
        (system_message, user_message) 元组。
    """
    system = f"""{agent.prompt_body}

{_COMMON_RULES}

你必须输出以下 JSON 结构：
{_get_agent_result_schema_desc()}

最多输出 {agent.max_findings} 条 finding。
risk_level 必须是 high / medium / low / info。
confidence 必须是 high / medium / low。"""

    user = f"""# 稿件

标题: {article.title}
栏目: {article.column or '未知'}
类型: {article.article_type}

# 稿件正文（分段）

{_format_segments(segments)}

# 知识库参考材料

{_format_context(context) if context else '本次没有检索到本地知识库材料，你只能基于稿件原文提出审稿意见。不得编造校规或历史案例。'}

# 任务

请审稿并输出 AgentResult JSON。最多输出 {agent.max_findings} 条 finding。"""

    return system, user


def _get_agent_result_schema_desc() -> str:
    return """{
  "agent_id": "your_agent_id",
  "agent_name": "你的名称",
  "status": "success",
  "findings": [
    {
      "finding_id": null,
      "agent_id": "your_agent_id",
      "agent_name": "你的名称",
      "risk_level": "high|medium|low|info",
      "confidence": "high|medium|low",
      "issue_type": "问题类型标签",
      "original_quote": "原文摘录",
      "segment_id": "s001",
      "problem": "问题描述",
      "possible_consequence": "可能后果",
      "suggestion": "修改建议",
      "evidence": [
        {"source_type": "article|rules|cases|style_guides|risky_phrases|examples", "source_id": "...", "quote": "...", "note": "..."}
      ],
      "tags": ["标签1"],
      "requires_attention": false
    }
  ],
  "summary": "审稿摘要"
}"""


def _format_segments(segments: list[ArticleSegment]) -> str:
    lines = []
    for s in segments:
        kind_label = {"title": "标题", "subtitle": "小标题", "body": "正文",
                      "caption": "图片标注", "unknown": "其他"}.get(s.kind, s.kind)
        lines.append(f"[{s.segment_id}][{kind_label}] {s.text}")
    return "\n".join(lines)


def _format_context(chunks: list[KnowledgeChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(
            f"[知识库材料 {i}]\n"
            f"source_type: {c.source_type}\n"
            f"source_id: {c.doc_id}\n"
            f"title: {c.title}\n"
            f"quote:\n{c.text}\n"
        )
    return "\n".join(parts)
