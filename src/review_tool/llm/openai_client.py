"""OpenAI 兼容客户端。"""

import os
import time
from .base import LLMClient, LLMResponse


class OpenAIClient(LLMClient):
    """OpenAI 兼容 LLM 客户端，支持自定义 base_url。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    async def complete_json(
        self,
        system: str,
        user: str,
        model: str = "default",
        temperature: float = 0.2,
        timeout_seconds: int = 90,
    ) -> LLMResponse:
        if model == "default":
            model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

        start = time.time()

        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=timeout_seconds,
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        latency = int((time.time() - start) * 1000)
        content = response.choices[0].message.content or ""

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            text=content,
            raw=response.model_dump(),
            token_usage=usage,
            latency_ms=latency,
        )
