"""Prompt 构造器：为 Selector 和各审稿 Agent 构造 system/user 消息。"""

import json
from ..schemas import (
    ArticleInput, ArticleSegment, AgentConfig, KnowledgeChunk, Finding, EvidenceRef,
)

_COMMON_RULES = """你必须输出 JSON。不得输出 Markdown 代码块的前后缀。
不得输出解释性文字。
所有问题必须绑定原文摘录 (original_quote)。
如果没有发现问题，findings 输出空数组 []。
不得编造规则、校规、授权事实、处分结果或不存在的依据。"""


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
    persona_rules = _get_persona_rules(agent)

    system = f"""{agent.prompt_body}

{_COMMON_RULES}
{persona_rules}

你必须输出以下 JSON 结构：
{_get_agent_result_schema_desc()}

最多输出 {agent.max_findings} 条 finding。
risk_level 必须是 high / medium / low / info。
confidence 必须是 high / medium / low。"""

    user = f"""# 稿件

标题: {article.title}
类型: {article.article_type}
事件背景: {article.event_background or '未填写'}

# 稿件正文（分段）

{_format_segments(segments)}

# 知识库参考材料

{_format_context(context) if context else '本次没有检索到本地知识库材料，你只能基于稿件原文提出审稿意见。不得编造规则、校规或不存在的依据。'}

# 任务

请审稿并输出 AgentResult JSON。最多输出 {agent.max_findings} 条 finding。"""

    return system, user


def _get_persona_rules(agent: AgentConfig) -> str:
    if agent.kind != "persona":
        return ""

    profile = agent.metadata.get("persona_profile") or {}
    if isinstance(profile, dict):
        mindset = profile.get("mindset") or ""
        stance = profile.get("stance") or "未指定"
        thinking_style = profile.get("thinking_style") or "未指定"
        concerns = profile.get("concerns") or []
        if isinstance(concerns, list):
            concerns_text = "、".join(str(item) for item in concerns) or "未指定"
        else:
            concerns_text = str(concerns)
    else:
        mindset = str(profile)
        stance = str(profile)
        thinking_style = "未指定"
        concerns_text = "未指定"

    return f"""
你当前是一个“立场画像模拟 Agent”，不是规则裁判。
你要模拟某一类真实读者或利益相关者的理解方式，但不得冒充、点名或声称代表任何具体真实个人。
核心模拟思路：
{mindset or '未指定'}

画像立场：{stance}
思维倾向：{thinking_style}
主要关切：{concerns_text}

请严格按照“核心模拟思路”阅读稿件，重点输出这类人可能产生的阅读反应、误解路径、反感点、信任下降点、被冒犯点、攻击点或传播动机。
如果提出修改建议，应说明怎样降低这类读者的误读或抵触。
不要把主观感受包装成事实结论；可以在 issue_type 或 tags 中标注 persona_response、reader_reaction、misreading_path。
"""


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
        {"source_type": "article|rules", "source_id": "...", "quote": "...", "note": "..."}
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
