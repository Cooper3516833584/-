"""结构化 LLM 调用：自动 JSON 解析 + Pydantic 校验 + 一次修复重试。"""

import json
import time
from pydantic import BaseModel
from .base import LLMClient, LLMResponse
from .json_repair import extract_json_text, JSONParseError


class InvalidLLMOutputError(Exception):
    """LLM 输出无法解析为期望的 Schema。"""
    pass


async def call_with_schema(
    llm_client: LLMClient,
    system: str,
    user: str,
    schema_model: type[BaseModel],
    model: str = "default",
    temperature: float = 0.2,
    timeout_seconds: int = 90,
    max_retries: int = 2,
) -> tuple[BaseModel, LLMResponse]:
    """调用 LLM 并将输出解析为指定的 Pydantic 模型。

    失败时自动重试一次 repair prompt。

    Args:
        llm_client: LLM 客户端。
        system: 系统消息。
        user: 用户消息。
        schema_model: 目标 Pydantic 模型类。
        model: 模型名称。
        temperature: 温度参数。
        timeout_seconds: 超时。
        max_retries: 最大重试次数。

    Returns:
        (parsed_model, llm_response) 元组。

    Raises:
        InvalidLLMOutputError: 所有重试均失败。
    """
    last_error: Exception | None = None
    last_raw: str = ""

    for attempt in range(max_retries + 1):
        try:
            response = await llm_client.complete_json(
                system=system,
                user=user,
                model=model,
                temperature=temperature,
                timeout_seconds=timeout_seconds,
            )
            last_raw = response.text

            json_text = extract_json_text(response.text)
            data = json.loads(json_text)
            parsed = schema_model.model_validate(data)
            return parsed, response

        except (JSONParseError, json.JSONDecodeError, Exception) as e:
            last_error = e
            if attempt < max_retries:
                # 构造 repair prompt
                user = _build_repair_prompt(user, last_raw, str(e), schema_model)
                temperature = 0.0  # repair 时用低温
            else:
                break

    raise InvalidLLMOutputError(
        f"LLM 输出在 {max_retries + 1} 次尝试后仍无法解析为 {schema_model.__name__}: {last_error}"
    )


def _build_repair_prompt(
    original_user: str,
    raw_output: str,
    error_msg: str,
    schema_model: type[BaseModel],
) -> str:
    """构造 JSON 修复 prompt。"""
    schema_fields = schema_model.model_fields

    return f"""下面是一个模型的输出，它应该符合指定的 JSON Schema，但解析失败。

原始任务：
{original_user[:1500]}

模型原始输出：
{raw_output[:2000]}

解析错误：
{error_msg}

预期 JSON Schema 关键字段：
{list(schema_fields.keys())}

请只返回修复后的合法 JSON，不要添加任何解释。如果原输出缺少 findings，请返回 findings: []。"""
