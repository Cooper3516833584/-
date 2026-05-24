# 04 Agent 配置文件规范

## 1. 目标

Agent 配置必须保存在项目根目录的 `agents/` 文件夹中，并且使用 txt 文件。

代码需要支持：

```text
新增 txt 文件即可新增 Agent。
修改 enabled 即可启用/禁用 Agent。
修改 applies_to 即可限制适用稿件类型或栏目。
Selector Agent 可以读取 Agent catalog 并决定启用哪些 Agent。
```

## 2. Agent 文件格式

每个 Agent txt 文件分两部分：

```text
YAML front matter：机器读取配置
正文 prompt_body：给 LLM 的角色说明和任务要求
```

完整示例：

```text
---
agent_id: risk_reviewer
name: 舆情风险审查员
enabled: true
kind: reviewer
priority: 90
applies_to:
  article_types: [news, commentary, interview, activity, notice, social_post, unknown]
  columns: ["*"]
capabilities:
  - public_opinion
  - misreading
  - group_conflict
knowledge_sources:
  - cases
  - rules
  - risky_phrases
max_findings: 10
model:
  name: default
  temperature: 0.2
  timeout_seconds: 90
  max_retries: 2
output_schema: AgentResult
---

# Role
你是……

# Review Focus
- ……

# Output Contract
必须输出 JSON。
```

## 3. 必填字段

```text
agent_id
name
enabled
kind
priority
output_schema
```

缺失必填字段时，`review-tool validate-config` 必须报错。

## 4. agent_id 规则

```text
必须是英文小写、数字、下划线。
不得包含空格。
不得与其它 Agent 重复。
Selector Agent 固定为 selector。
```

示例：

```text
selector
fact_checker
risk_reviewer
privacy_reviewer
copyright_reviewer
interview_ethics_reviewer
club_activity_reviewer
```

## 5. kind 规则

第一版只需要：

```text
selector：自动选择 Agent 的 Agent，全项目只能有一个。
reviewer：普通审稿 Agent。
```

预留但不实现：

```text
arbitrator：未来可做 LLM 仲裁。
rewriter：未来可做改写 Agent。
```

## 6. enabled 规则

```text
enabled: true  表示可被 Selector 选择和执行。
enabled: false 表示加载但不参与执行。
```

Selector Agent 不应看到 disabled Agent，或者看到但必须标明不可用。推荐第一版直接不把 disabled Agent 放入 Selector catalog。

## 7. priority 规则

priority 用于排序，不代表一定启用。

```text
Selector 选择后，系统按 priority 从高到低排序执行。
相同 priority 按 agent_id 字母序排序。
```

推荐默认：

```text
selector: 100
risk_reviewer: 90
privacy_reviewer: 85
fact_checker: 80
copyright_reviewer: 75
interview_ethics_reviewer: 70
audience_reviewer: 60
format_reviewer: 50
```

## 8. applies_to 规则

示例：

```yaml
applies_to:
  article_types: [interview, unknown]
  columns: [人物, 校友, "*"]
```

匹配逻辑：

```text
如果 article_types 包含 "*"，任意稿件类型都适用。
如果 columns 包含 "*"，任意栏目都适用。
否则必须 article_type 和 column 至少满足配置条件。
```

注意：Selector 可以推荐一个 Agent，但代码层仍要检查 applies_to。若不匹配，默认跳过，除非 SelectorResult 中该 Agent reason 强烈说明必要性。第一版建议严格跳过。

## 9. capabilities 规则

capabilities 是给 Selector Agent 看的能力标签。

示例：

```yaml
capabilities:
  - privacy
  - authorization
  - image_rights
```

Selector Agent catalog 中应该只提供简化信息：

```json
{
  "agent_id": "privacy_reviewer",
  "name": "隐私与授权审查员",
  "capabilities": ["privacy", "authorization", "image_rights"],
  "applies_to": {"article_types": ["news", "interview", "unknown"]},
  "priority": 85
}
```

不要把完整 prompt_body 全部塞给 Selector Agent，以免上下文过长。

## 10. knowledge_sources 规则

表示该 Agent 需要哪些知识库：

```yaml
knowledge_sources:
  - rules
  - cases
  - risky_phrases
```

运行 Agent 前，系统根据这些 sources 从检索结果中过滤上下文。

如果 Agent 没写 knowledge_sources，则默认给：

```text
rules
cases
style_guides
risky_phrases
examples
```

但建议每个 Agent 显式声明。

## 11. max_findings 规则

限制单个 Agent 最多输出多少条问题。

目的：防止 Agent 为了挑刺输出过多低价值建议。

推荐：

```text
risk_reviewer: 10
privacy_reviewer: 8
fact_checker: 8
audience_reviewer: 8
format_reviewer: 12
copyright_reviewer: 8
```

PromptBuilder 必须把 max_findings 写进 Agent 输入中。

## 12. model 配置

```yaml
model:
  name: default
  temperature: 0.2
  timeout_seconds: 90
  max_retries: 2
```

说明：

```text
name=default 表示使用 .env 或 config.py 中的默认模型。
temperature 建议审稿类任务 0.1 到 0.3。
timeout_seconds 是单个 Agent 超时时间。
max_retries 是 LLM 调用失败重试次数，不包括 JSON 修复。
```

## 13. prompt_body 规则

front matter 后面的正文就是 prompt_body。

代码不关心里面具体写什么，但 PromptBuilder 需要把它与标准输出要求拼接。

最终给 LLM 的内容建议由三块组成：

```text
1. 通用系统规则：必须引用原文、必须输出 JSON、不得编造事实。
2. Agent 自己的 prompt_body。
3. 本次稿件、段落、知识库上下文、输出 schema。
```

## 14. AgentLoader 实现要求

文件：

```text
src/review_tool/loaders/agent_loader.py
```

函数：

```python
def load_agent_configs(agent_dir: Path) -> list[AgentConfig]:
    ...
```

必须做：

```text
遍历 agents/*.txt
解析 front matter
构造 AgentConfig
检查 agent_id 唯一
检查只有一个 kind=selector
检查 selector 必须 enabled
返回排序后的 AgentConfig 列表
```

## 15. AgentRegistry 实现要求

文件：

```text
src/review_tool/agents/registry.py
```

接口：

```python
class AgentRegistry:
    def __init__(self, configs: list[AgentConfig]): ...
    def get(self, agent_id: str) -> AgentConfig: ...
    def exists(self, agent_id: str) -> bool: ...
    def list_enabled_reviewers(self) -> list[AgentConfig]: ...
    def get_selector(self) -> AgentConfig: ...
    def build_catalog_for_selector(self) -> list[dict]: ...
```

`build_catalog_for_selector()` 只返回轻量字段：

```text
agent_id
name
priority
capabilities
applies_to
knowledge_sources
```

不要返回 prompt_body。
