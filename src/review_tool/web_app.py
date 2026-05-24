"""本地 Web UI 服务。"""

from __future__ import annotations

import asyncio
import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from .config import load_settings
from .engine import ReviewEngine, build_review_output_paths
from .loaders.agent_loader import load_agent_configs
from .schemas import ArticleInput

STATIC_DIR = Path(__file__).resolve().parent / "web_static"

SETTINGS_FIELDS = [
    ("LLM_PROVIDER", "openai"),
    ("OPENAI_API_KEY", ""),
    ("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    ("OPENAI_MODEL", "gpt-4.1-mini"),
    ("MOCK_MODE", "false"),
    ("DEFAULT_MODEL_NAME", "default"),
    ("DEFAULT_TEMPERATURE", "0.2"),
    ("DEFAULT_TIMEOUT_SECONDS", "90"),
    ("DEFAULT_MAX_RETRIES", "2"),
    ("REVIEWER_OUTPUT_SCHEMA", "AgentResult"),
    ("SELECTOR_OUTPUT_SCHEMA", "SelectorResult"),
    ("ALWAYS_INCLUDE_BASE_AGENTS", "true"),
    ("BASE_AGENT_IDS", "fact_checker,risk_reviewer,audience_reviewer,format_reviewer,privacy_reviewer"),
    ("MAX_SELECTED_AGENTS", "10"),
    ("RETRIEVAL_TOP_K", "12"),
    ("MAX_CONCURRENCY", "5"),
    ("AGENT_TIMEOUT_SECONDS", "120"),
    ("DEBUG", "false"),
]

SETTING_DEFAULTS = dict(SETTINGS_FIELDS)
AGENT_ID_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,63}$")


def run_web_server(project_root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    """启动本地 Web UI。"""
    root = project_root.resolve()
    handler = _make_handler(root)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Web UI: http://{host}:{port}")
    server.serve_forever()


def _make_handler(project_root: Path):
    class ReviewToolHandler(BaseHTTPRequestHandler):
        server_version = "ReviewToolWeb/0.1"

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = unquote(parsed.path)

            if path == "/":
                self._serve_static("index.html")
                return
            if path.startswith("/static/"):
                self._serve_static(path.removeprefix("/static/"))
                return
            if path == "/api/agents":
                agents = _list_agents(project_root)
                self._send_json(
                    {
                        "agents": agents,
                        "capability_tags": _capability_tags(agents),
                    }
                )
                return
            if path == "/api/settings":
                self._send_json({"settings": _read_settings(project_root)})
                return
            if path.startswith("/output/"):
                self._serve_output(path.removeprefix("/output/"))
                return

            self._send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            try:
                payload = self._read_json()
                if path == "/api/agents":
                    agent = _create_agent(project_root, payload)
                    status = HTTPStatus.OK if agent.get("already_exists") else HTTPStatus.CREATED
                    self._send_json({"agent": agent}, status)
                    return
                if path == "/api/settings":
                    settings = _write_settings(project_root, payload)
                    self._send_json({"settings": settings})
                    return
                if path == "/api/review":
                    result = _run_review(project_root, payload)
                    self._send_json(result)
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Not found")
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:  # pragma: no cover - defensive for UI errors
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

        def log_message(self, format: str, *args) -> None:
            return

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("请求体不是合法 JSON") from exc
            if not isinstance(data, dict):
                raise ValueError("请求体必须是 JSON 对象")
            return data

        def _send_json(self, data: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            self._send_json({"error": message}, status)

        def _serve_static(self, relative: str) -> None:
            path = (STATIC_DIR / relative).resolve()
            if not _is_within(path, STATIC_DIR) or not path.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "Static file not found")
                return
            self._serve_file(path)

        def _serve_output(self, relative: str) -> None:
            output_dir = (project_root / "output").resolve()
            path = (output_dir / relative).resolve()
            if not _is_within(path, output_dir) or not path.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "Output file not found")
                return
            self._serve_file(path)

        def _serve_file(self, path: Path) -> None:
            content = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", _content_type(path))
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    return ReviewToolHandler


def _list_agents(project_root: Path) -> list[dict]:
    configs = load_agent_configs(project_root / "agents")
    return [
        {
            "agent_id": config.agent_id,
            "name": config.name,
            "enabled": config.enabled,
            "kind": config.kind,
            "priority": config.priority,
            "capabilities": config.capabilities,
            "max_findings": config.max_findings,
            "persona_profile": config.metadata.get("persona_profile", {}),
        }
        for config in configs
    ]


def _capability_tags(agents: list[dict]) -> list[str]:
    tags: set[str] = set()
    for agent in agents:
        for tag in agent.get("capabilities") or []:
            if str(tag).strip():
                tags.add(str(tag).strip())
    return sorted(tags)


def _create_agent(project_root: Path, payload: dict) -> dict:
    agent_id = str(payload.get("agent_id", "")).strip()
    if not AGENT_ID_RE.fullmatch(agent_id):
        raise ValueError("agent_id 需以字母开头，只能包含字母、数字和下划线，长度 3-64")

    agents_dir = project_root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / f"{agent_id}.txt"
    if path.exists():
        existing = _agent_file_to_dict(path)
        existing["already_exists"] = True
        return existing

    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("请填写 Agent 中文名")

    kind = str(payload.get("kind", "reviewer")).strip() or "reviewer"
    if kind not in {"reviewer", "persona"}:
        raise ValueError("Agent 类型只能是 reviewer 或 persona")

    persona_mindset = str(payload.get("persona_mindset", "")).strip()
    if kind == "persona" and not persona_mindset:
        raise ValueError("请填写模拟思路")

    review_focus = str(payload.get("review_focus", "")).strip()
    if not review_focus:
        if kind == "persona":
            review_focus = "根据模拟思路阅读稿件，输出可能的误读、反感、攻击点和改写建议。"
        else:
            raise ValueError("请填写审稿关注点")

    default_capabilities = ["persona_response"] if kind == "persona" else ["custom_review"]
    capabilities = _split_items(payload.get("capabilities", default_capabilities)) or default_capabilities
    priority = _as_int(payload.get("priority"), 50)
    max_findings = _as_int(payload.get("max_findings"), 8)
    enabled = _as_bool(payload.get("enabled"), True)

    lines = [
        "---",
        "# Agent 唯一标识，不能和其他 Agent 重复。",
        f"agent_id: {agent_id}",
        "# 报告、日志和配置校验中显示的名称。",
        f"name: {_yaml_scalar(name)}",
        "# 是否启用；false 表示不会被 Selector 选择或执行。",
        f"enabled: {str(enabled).lower()}",
        "# Agent 类型；reviewer 表示规则审查 Agent，persona 表示立场画像模拟 Agent。",
        f"kind: {kind}",
        "# 优先级；数字越大越优先展示给 Selector。",
        f"priority: {priority}",
        "# 能力标签，帮助 Selector 判断这个 Agent 适合审什么。",
        "capabilities:",
    ]
    lines.extend(f"  - {_yaml_scalar(item)}" for item in capabilities)
    if kind == "persona":
        lines.extend(
            [
                "# persona_profile.mindset 用自然语言描述这个模拟读者的思路、偏见和阅读心态。",
                "persona_profile:",
                f"  mindset: {_yaml_scalar(persona_mindset)}",
                "  stance: 立场画像模拟",
                "  thinking_style: 按模拟思路阅读稿件",
                "  concerns:",
                "    - 误读路径",
                "    - 反感点",
                "    - 攻击点",
            ]
        )
    lines.extend(
        [
            "# 单次最多输出的审稿意见数量。",
            f"max_findings: {max_findings}",
            "---",
            "",
            "# Role",
            f"你是{name}。",
            "",
        ]
    )
    if kind == "persona":
        lines.extend(
            [
                "# Persona Mindset",
                persona_mindset,
                "",
            ]
        )
    lines.extend(
        [
            "# Review Focus",
        ]
    )
    lines.extend(f"- {item}" for item in _split_lines(review_focus))
    lines.extend(
        [
            "",
            "# Output Boundary",
            "- 只输出 AgentResult JSON。",
            "- 每条意见必须绑定稿件原文摘录。",
            "- 如果是立场画像模拟，请说明这类读者为什么会这样理解或攻击，不要声称代表任何具体真实个人。",
            "- 如果使用本地知识库依据，只能引用 rules/ 中的规则材料。",
            "- 不编造不存在的规则或事实。",
        ]
    )

    path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "agent_id": agent_id,
        "name": name,
        "enabled": enabled,
        "kind": kind,
        "priority": priority,
        "capabilities": capabilities,
        "max_findings": max_findings,
        "persona_profile": {"mindset": persona_mindset} if kind == "persona" else {},
    }


def _run_review(project_root: Path, payload: dict) -> dict:
    title = str(payload.get("title", "")).strip()
    body = str(payload.get("body", "")).strip()
    if not title:
        raise ValueError("请填写稿件标题")
    if not body:
        raise ValueError("请填写稿件正文")

    settings = load_settings(project_root)
    engine = ReviewEngine(project_root=project_root, settings=settings)
    article = ArticleInput(
        title=title,
        body=body,
        article_type=str(payload.get("article_type", "unknown") or "unknown"),  # type: ignore[arg-type]
        event_background=str(payload.get("event_background", "")).strip() or None,
    )

    mode = str(payload.get("mode", "auto"))
    manual_agent_ids = None
    if mode == "manual":
        manual_agent_ids = [
            str(item).strip()
            for item in payload.get("agent_ids", [])
            if str(item).strip()
        ]

    result = asyncio.run(
        engine.review_article(
            article=article,
            output_dir=project_root / "output",
            manual_agent_ids=manual_agent_ids,
        )
    )

    summary = result.final_report.get("summary", {})
    _, report_docx_path, report_json_path = build_review_output_paths(
        result.article,
        project_root / "output",
        result.run_id,
    )
    return {
        "run_id": result.run_id,
        "selected_agent_ids": result.selected_agent_ids,
        "summary": summary,
        "warnings": result.warnings,
        "errors": result.errors,
        "report_docx_url": _output_url(project_root, report_docx_path),
        "report_json_url": _output_url(project_root, report_json_path),
    }


def _read_settings(project_root: Path) -> dict:
    env_values = _read_env_file(project_root / ".env")
    return {
        key: env_values.get(key, default)
        for key, default in SETTINGS_FIELDS
    }


def _write_settings(project_root: Path, payload: dict) -> dict:
    current = _read_env_file(project_root / ".env")
    incoming = payload.get("settings", payload)
    if not isinstance(incoming, dict):
        raise ValueError("settings 必须是对象")

    for key, default in SETTINGS_FIELDS:
        value = incoming.get(key, current.get(key, default))
        current[key] = str(value).strip()

    lines = [f"{key}={_format_env_value(current[key])}" for key, _ in SETTINGS_FIELDS]
    extra_keys = sorted(k for k in current if k not in SETTING_DEFAULTS)
    lines.extend(f"{key}={_format_env_value(current[key])}" for key in extra_keys)
    (project_root / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return _read_settings(project_root)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _unquote_env_value(value.strip())
    return values


def _format_env_value(value: str) -> str:
    if value == "":
        return ""
    if any(ch.isspace() for ch in value) or "#" in value or '"' in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def _output_url(project_root: Path, path: Path) -> str:
    output_dir = (project_root / "output").resolve()
    relative = path.resolve().relative_to(output_dir).as_posix()
    return f"/output/{quote(relative, safe='/')}"


def _agent_file_to_dict(path: Path) -> dict:
    configs = load_agent_configs(path.parent)
    for item in configs:
        if item.agent_id == path.stem:
            return {
                "agent_id": item.agent_id,
                "name": item.name,
                "enabled": item.enabled,
                "kind": item.kind,
                "priority": item.priority,
                "capabilities": item.capabilities,
                "max_findings": item.max_findings,
                "persona_profile": item.metadata.get("persona_profile", {}),
            }
    return {"agent_id": path.stem}


def _split_items(value) -> list[str]:
    if isinstance(value, list):
        raw_items = [str(item) for item in value]
    else:
        raw_items = re.split(r"[,，\n]+", str(value))
    return [item.strip() for item in raw_items if item.strip()]


def _yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _split_lines(value: str) -> list[str]:
    return [line.strip("- ").strip() for line in value.splitlines() if line.strip()]


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "是"}


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(suffix, "application/octet-stream")
