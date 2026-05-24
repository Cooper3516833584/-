# 05 Selector Agent 自动选择 Agent 机制

## 1. 目标

用户要求：第一个 Agent 拿到稿件内容后，自主判断并启用对应 Agent。

因此系统必须实现一个固定入口 Agent：`selector`。

执行顺序：

```text
稿件预处理
  ↓
构建 Agent Catalog
  ↓
Selector Agent 读取稿件摘要、段落、元信息、Agent Catalog
  ↓
Selector Agent 输出 SelectorResult
  ↓
代码层校验、补全、兜底
  ↓
得到 selected_agent_ids
```

## 2. Selector Agent 文件

固定文件：

```text
agents/00_selector_agent.txt
```

front matter：

```text
---
agent_id: selector
name: Agent选择器
enabled: true
kind: selector
priority: 100
model:
  name: default
  temperature: 0.1
  timeout_seconds: 60
  max_retries: 2
output_schema: SelectorResult
---

# Role
你负责根据稿件内容和可用 Agent Catalog 判断本次审稿应启用哪些 Agent。

# Task Boundary
你只选择 Agent，不直接审稿。
你不输出具体修改意见。
你不替代后续审稿 Agent。
```

具体 prompt 以后可以细化，但输出 Schema 必须现在固定。

## 3. Selector 输入

Selector Agent 的输入对象应包含：

```python
class SelectorInput(BaseModel):
    article: ArticleInput
    segments: list[ArticleSegment]
    agent_catalog: list[dict]
    available_knowledge_sources: list[str]
    deterministic_hints: dict
```

其中 deterministic_hints 由代码预分析生成：

```json
{
  "has_images": true,
  "paragraph_count": 12,
  "title_contains_question_mark": false,
  "possible_interview": true,
  "possible_notice": false,
  "sensitive_keywords_found": ["投诉", "处分"],
  "article_type_guess_by_rules": "interview"
}
```

## 4. Agent Catalog

Selector 不应读取全部 Agent prompt，只读取能力摘要。

示例：

```json
[
  {
    "agent_id": "fact_checker",
    "name": "事实与逻辑核查员",
    "priority": 80,
    "capabilities": ["fact", "logic", "consistency"],
    "applies_to": {"article_types": ["*"]},
    "knowledge_sources": ["rules", "cases"]
  },
  {
    "agent_id": "privacy_reviewer",
    "name": "隐私与授权审查员",
    "priority": 85,
    "capabilities": ["privacy", "authorization", "image_rights"],
    "applies_to": {"article_types": ["news", "interview", "activity", "social_post", "unknown"]},
    "knowledge_sources": ["rules", "cases", "risky_phrases"]
  }
]
```

## 5. Selector 输出

必须符合 `SelectorResult`：

```json
{
  "status": "success",
  "detected_article_type": "interview",
  "detected_tags": ["interview", "privacy", "quote_integrity"],
  "selected_agents": [
    {
      "agent_id": "fact_checker",
      "reason": "稿件包含具体事件、时间和人物，需要核查事实一致性。",
      "priority": 80
    },
    {
      "agent_id": "interview_ethics_reviewer",
      "reason": "稿件疑似采访稿，包含受访者表述和引语，需要检查授权与断章取义风险。",
      "priority": 70
    }
  ],
  "context_queries": [
    "采访授权",
    "受访者引语完整性",
    "学生个人信息保护"
  ],
  "reasoning_summary": "稿件更像人物采访或事件采访，重点风险是授权、引语完整性和隐私。",
  "warnings": []
}
```

## 6. 代码层校验

Selector 输出不能直接信任。必须实现：

```python
def validate_selector_result(
    result: SelectorResult,
    registry: AgentRegistry,
    article: ArticleInput,
) -> SelectorResult:
    ...
```

校验规则：

```text
1. selected_agents 中 agent_id 必须存在。
2. agent_id 不能是 selector。
3. Agent 必须 enabled。
4. Agent kind 必须是 reviewer。
5. Agent applies_to 必须匹配稿件类型或 unknown。
6. 重复 agent_id 去重。
7. selected_agents 不能超过 max_selected_agents。
8. 如果 selected_agents 为空，走兜底策略。
```

## 7. 必跑基础 Agent

即使 Selector 没选，也建议第一版强制补充基础 Agent。

基础 Agent：

```text
fact_checker
risk_reviewer
audience_reviewer
format_reviewer
privacy_reviewer
```

原因：

```text
Selector 可能漏选。
这些是通用审稿维度。
单次工具更重视召回，而不是极限节省 token。
```

如果用户后续希望减少成本，可以通过配置关闭 `always_include_base_agents`。

配置项：

```python
class ReviewSettings(BaseModel):
    always_include_base_agents: bool = True
    base_agent_ids: list[str] = [
        "fact_checker",
        "risk_reviewer",
        "audience_reviewer",
        "format_reviewer",
        "privacy_reviewer",
    ]
    max_selected_agents: int = 10
```

## 8. 兜底选择规则

如果 Selector 调用失败、输出非法、或选不到任何 Agent，使用 deterministic fallback。

```python
def fallback_select_agents(article: ArticleInput, hints: dict, registry: AgentRegistry) -> list[str]:
    selected = set(settings.base_agent_ids)

    if hints.get("has_images"):
        selected.add("copyright_reviewer")

    if hints.get("possible_interview"):
        selected.add("interview_ethics_reviewer")

    if hints.get("title_risk"):
        selected.add("title_reviewer")

    return [a for a in selected if registry.exists(a) and registry.get(a).enabled]
```

## 9. Deterministic Hints 实现

文件：

```text
src/review_tool/review/routing.py
```

函数：

```python
def build_deterministic_hints(article: ArticleInput, segments: list[ArticleSegment]) -> dict:
    ...
```

规则示例：

```text
possible_interview：正文包含“采访”“受访者”“他说”“她表示”“问：”“答：”
possible_notice：标题或正文包含“通知”“公示”“报名”“截止”“时间地点”
possible_activity：包含“活动”“现场”“参与者”“报名”“举办”
title_risk：标题包含“震惊”“曝光”“怒了”“所有人都”“必须看”等词
has_images：images 非空或正文包含 Markdown 图片语法
sensitive_keywords_found：命中 risky_phrases 下的关键词
```

## 10. Selector 与知识检索的关系

Selector 输出 `context_queries`，知识检索器使用这些 query 扩展检索。

检索查询应包含：

```text
稿件标题
稿件前 300 字摘要
Selector context_queries
Selector detected_tags
deterministic_hints 中的关键词
```

## 11. Selector 执行结果保存

每次运行保存：

```text
output/{run_id}/selector_result.json
```

内容包括：

```text
raw_output
parsed_result
validated_selected_agent_ids
fallback_used
warnings
```

## 12. Selector 的失败处理

失败分类：

```text
llm_error：LLM 调用失败
json_error：输出不是 JSON
schema_error：JSON 不符合 SelectorResult
empty_selection：没有选出 Agent
invalid_agent_ids：全是不存在的 Agent
```

处理规则：

```text
记录到 warnings。
启用 fallback_select_agents。
审稿继续。
最终报告中显示“Selector Agent 失败，已启用兜底 Agent 组合”。
```

## 13. 验收测试

必须写测试：

```text
test_selector_rejects_unknown_agent_id
test_selector_deduplicates_agents
test_selector_fallback_when_empty
test_selector_adds_base_agents
test_selector_skips_disabled_agent
test_selector_respects_max_selected_agents
```
