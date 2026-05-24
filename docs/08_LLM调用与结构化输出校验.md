# 08 LLM 调用与结构化输出校验

## 1. 目标

所有 LLM 调用必须经过统一封装。不要在 AgentRunner、Selector、Arbitrator 中直接调用具体供应商 SDK。

目标：

```text
统一超时
统一重试
统一 JSON 输出约束
统一 token usage 记录
统一错误类型
方便以后更换模型供应商
```

## 2. LLMClient 抽象

文件：

```text
src/review_tool/llm/base.py
```

接口：

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class LLMResponse(BaseModel):
    text: str
    raw: dict | None = None
    token_usage: dict = {}
    latency_ms: int | None = None

class LLMClient(ABC):
    @abstractmethod
    async def complete_json(
        self,
        system: str,
        user: str,
        model: str,
        temperature: float,
        timeout_seconds: int,
    ) -> LLMResponse:
        ...
```

## 3. OpenAIClient 实现

文件：

```text
src/review_tool/llm/openai_client.py
```

要求：

```text
从环境变量读取 API key。
支持 default model。
支持异步调用。
尽量使用 JSON 模式或结构化输出能力。
失败时抛统一异常。
```

环境变量：

```text
LLM_PROVIDER=openai
OPENAI_API_KEY=xxx
OPENAI_BASE_URL=可选
OPENAI_MODEL=gpt-4.1-mini 或其它模型名
```

不要在代码中写死模型。

## 4. MockLLMClient

必须实现 mock，方便测试。

文件：

```text
src/review_tool/llm/mock_client.py
```

功能：

```text
根据 system/user 中的关键词返回固定 JSON。
用于单元测试和无 API key 环境。
```

## 5. PromptBuilder

文件：

```text
src/review_tool/agents/prompt_builder.py
```

接口：

```python
def build_selector_prompt(...)-> tuple[str, str]: ...
def build_reviewer_prompt(...)-> tuple[str, str]: ...
```

系统消息建议包含通用规则：

```text
你必须输出 JSON。
不得输出 Markdown。
不得输出解释性前后缀。
不得编造校规、历史案例、处分结果。
所有问题必须绑定原文摘录。
如果没有问题，findings 输出空数组。
```

用户消息包含：

```text
Agent 角色说明
稿件元信息
稿件分段
知识库材料
输出 JSON Schema 摘要
本次 max_findings
```

## 6. JSON 提取

即使要求 JSON，模型也可能包裹 Markdown 代码块。

文件：

```text
src/review_tool/llm/json_repair.py
```

实现：

```python
def extract_json_text(text: str) -> str:
    """从 LLM 输出中提取最可能的 JSON 字符串。"""
```

规则：

```text
如果 text 是合法 JSON，直接返回。
如果包含 ```json ... ```，提取代码块。
否则找到第一个 { 或 [ 到最后一个 } 或 ]。
仍失败则抛 JSONParseError。
```

## 7. 结构化调用函数

文件：

```text
src/review_tool/llm/structured.py
```

接口：

```python
async def call_with_schema(
    llm_client: LLMClient,
    system: str,
    user: str,
    schema_model: type[BaseModel],
    model: str,
    temperature: float,
    timeout_seconds: int,
    max_retries: int = 2,
) -> tuple[BaseModel, LLMResponse]:
    ...
```

流程：

```text
1. 调用 LLM。
2. 提取 JSON。
3. json.loads。
4. Pydantic model_validate。
5. 如果失败，调用一次 repair prompt。
6. 仍失败则抛 InvalidLLMOutputError。
```

## 8. Repair Prompt

当 JSON 解析失败时，只做一次修复。

修复输入：

```text
下面是一个模型输出，它应该符合某个 JSON Schema，但现在无法解析或字段不完整。
请只返回修复后的 JSON，不要解释。
```

注意：

```text
修复只改格式，不新增实质审稿意见。
如果原输出缺少 findings，可以返回 findings: []。
```

## 9. AgentRunner

文件：

```text
src/review_tool/agents/runner.py
```

接口：

```python
class AgentRunner:
    def __init__(self, llm_client: LLMClient): ...

    async def run_reviewer(
        self,
        agent: AgentConfig,
        article: ArticleInput,
        segments: list[ArticleSegment],
        context: list[KnowledgeChunk],
    ) -> AgentResult:
        ...
```

实现要求：

```text
构造 prompt。
调用 call_with_schema(schema_model=AgentResult)。
补充 agent_id、agent_name。
为每条 finding 补 finding_id。
记录 latency、token_usage。
异常时返回 status=failed 的 AgentResult。
```

## 10. SelectorRunner

文件：

```text
src/review_tool/agents/selector.py
```

接口：

```python
async def run_selector(...)-> tuple[SelectorResult, dict]:
    ...
```

要求：

```text
调用 selector Agent。
如果失败，返回 status=failed 的 SelectorResult，而不是抛出到顶层。
同时 debug 中记录 raw_output 和 error。
```

## 11. 输出字段补全

模型可能漏掉 agent_id、agent_name。系统补全：

```python
for finding in result.findings:
    finding.agent_id = agent.agent_id
    finding.agent_name = agent.name
    if not finding.finding_id:
        finding.finding_id = make_finding_id(...)
```

## 12. 无问题输出

Agent 没有发现问题时必须输出：

```json
{
  "agent_id": "privacy_reviewer",
  "agent_name": "隐私与授权审查员",
  "status": "success",
  "findings": [],
  "summary": "未发现明显隐私与授权风险。"
}
```

不要让 Agent 输出自然语言“没问题”。

## 13. 验收测试

必须写：

```text
test_extract_json_plain_object
test_extract_json_from_markdown_codeblock
test_call_with_schema_validates_pydantic
test_invalid_output_returns_failed_agent_result
test_agent_runner_fills_agent_id_and_finding_id
test_selector_runner_returns_failed_result_on_exception
```
