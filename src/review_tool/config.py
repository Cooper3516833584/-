"""配置管理，从环境变量和 .env 文件读取设置。"""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv


def _load_dotenv(project_root: Path) -> None:
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)


class ReviewSettings(BaseModel):
    """审稿全局设置。"""

    project_root: str = "."
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    mock_mode: bool = False
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
        mock_mode=os.getenv("MOCK_MODE", "").lower() in ("1", "true", "yes"),
        debug=os.getenv("DEBUG", "").lower() in ("1", "true", "yes"),
    )
