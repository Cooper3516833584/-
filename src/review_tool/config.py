"""配置管理，从环境变量和 .env 文件读取设置。"""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv


def _load_dotenv(project_root: Path) -> None:
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


class ReviewSettings(BaseModel):
    """审稿全局设置。"""

    project_root: str = "."
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    mock_mode: bool = False
    default_model_name: str = "default"
    default_temperature: float = 0.2
    default_timeout_seconds: int = 90
    default_max_retries: int = 2
    reviewer_output_schema: str = "AgentResult"
    selector_output_schema: str = "SelectorResult"
    always_include_base_agents: bool = True
    base_agent_ids: list[str] = Field(
        default_factory=lambda: [
            "fact_checker",
            "risk_reviewer",
            "audience_reviewer",
            "format_reviewer",
            "privacy_reviewer",
        ]
    )
    max_selected_agents: int = 10
    retrieval_top_k: int = 12
    max_concurrency: int = 5
    agent_timeout_seconds: int = 120
    debug: bool = False


def load_settings(project_root: Path | None = None) -> ReviewSettings:
    """从环境变量加载设置。"""
    root = project_root or Path(".")
    _load_dotenv(root)

    return ReviewSettings(
        project_root=str(root.resolve()),
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        mock_mode=_env_bool("MOCK_MODE", False),
        default_model_name=os.getenv("DEFAULT_MODEL_NAME", "default"),
        default_temperature=_env_float("DEFAULT_TEMPERATURE", 0.2),
        default_timeout_seconds=_env_int("DEFAULT_TIMEOUT_SECONDS", 90),
        default_max_retries=_env_int("DEFAULT_MAX_RETRIES", 2),
        reviewer_output_schema=os.getenv("REVIEWER_OUTPUT_SCHEMA", "AgentResult"),
        selector_output_schema=os.getenv("SELECTOR_OUTPUT_SCHEMA", "SelectorResult"),
        always_include_base_agents=_env_bool("ALWAYS_INCLUDE_BASE_AGENTS", True),
        base_agent_ids=_env_list(
            "BASE_AGENT_IDS",
            ["fact_checker", "risk_reviewer", "audience_reviewer", "format_reviewer", "privacy_reviewer"],
        ),
        max_selected_agents=_env_int("MAX_SELECTED_AGENTS", 10),
        retrieval_top_k=_env_int("RETRIEVAL_TOP_K", 12),
        max_concurrency=_env_int("MAX_CONCURRENCY", 5),
        agent_timeout_seconds=_env_int("AGENT_TIMEOUT_SECONDS", 120),
        debug=_env_bool("DEBUG", False),
    )
