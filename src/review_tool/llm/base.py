"""LLM 客户端抽象基类。"""

from abc import ABC, abstractmethod
from pydantic import BaseModel


class LLMResponse(BaseModel):
    text: str
    raw: dict | None = None
    token_usage: dict = {}
    latency_ms: int | None = None


class LLMClient(ABC):
    """LLM 客户端抽象。所有 LLM 调用必须通过此接口。"""

    @abstractmethod
    async def complete_json(
        self,
        system: str,
        user: str,
        model: str = "default",
        temperature: float = 0.2,
        timeout_seconds: int = 90,
    ) -> LLMResponse:
        """发送请求并返回 LLMResponse。"""
        ...
