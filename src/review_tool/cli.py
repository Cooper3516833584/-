"""CLI 入口：review-tool 命令。"""

import asyncio
import sys
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from .config import load_settings
from .engine import ReviewEngine
from .loaders.agent_loader import load_agent_configs
from .loaders.corpus_loader import load_corpus
from .knowledge.chunker import chunk_documents
from .knowledge.index_cache import save_cache
from .review.preprocess import load_article_file, preprocess_article
from .review.routing import (
    build_deterministic_hints,
    validate_selector_result,
    finalize_selected_agents,
)
from .llm.base import LLMClient
from .llm.mock_client import MockLLMClient
from .llm.openai_client import OpenAIClient

app = typer.Typer(name="review-tool", help="高校学生媒体单次智能审稿工具")
console = Console()


def _get_engine(project_root: Path) -> ReviewEngine:
    settings = load_settings(project_root)
    return ReviewEngine(project_root=project_root, settings=settings)


def _get_llm_client(project_root: Path) -> LLMClient:
    settings = load_settings(project_root)
    if settings.mock_mode:
        return MockLLMClient()
    return OpenAIClient(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


@app.command()
def review(
    article_path: Path = typer.Argument(..., help="待审稿件路径"),
    project_root: Path = typer.Option(Path("."), "--project-root", "-r", help="项目根目录"),
    output: Path = typer.Option(Path("output"), "--output", "-o", help="输出目录"),
    debug: bool = typer.Option(False, "--debug", help="开启 debug 模式"),
    mock: bool = typer.Option(False, "--mock", help="使用 Mock LLM（无需 API key）"),
):
    """审稿主命令：对指定稿件执行完整审稿流程。"""
    try:
        settings = load_settings(project_root)
        if mock:
            settings.mock_mode = True
        if debug:
            settings.debug = True

        engine = ReviewEngine(project_root=project_root, settings=settings)
        result = asyncio.run(engine.review_file(article_path, output))

        summary = result.final_report.get("summary", {})
        must_fix = summary.get("must_fix_count", 0)
        should_fix = summary.get("should_fix_count", 0)

        console.print()
        console.print("[bold green]审稿完成。[/bold green]")
        console.print(f"run_id: {result.run_id}")
        console.print(f"报告: {output.resolve() / result.run_id / 'report.md'}")
        console.print(f"必须修改: [bold red]{must_fix}[/bold red]")
        console.print(f"建议修改: [bold yellow]{should_fix}[/bold yellow]")

        for w in result.warnings:
            console.print(f"[yellow]警告: {w}[/yellow]")

        if result.errors:
            console.print(f"[red]错误数: {len(result.errors)}[/red]")

    except FileNotFoundError as e:
        console.print(f"[red]文件不存在: {e}[/red]")
        raise typer.Exit(code=1)
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]未预期的错误: {e}[/red]")
        if debug:
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=1)


@app.command()
def select_agents(
    article_path: Path = typer.Argument(..., help="待审稿件路径"),
    project_root: Path = typer.Option(Path("."), "--project-root", "-r", help="项目根目录"),
    mock: bool = typer.Option(True, "--mock/--no-mock", help="使用 Mock LLM"),
):
    """只运行 Selector Agent，显示它会选择哪些审稿 Agent。"""
    try:
        settings = load_settings(project_root)
        if mock:
            settings.mock_mode = True

        engine = ReviewEngine(project_root=project_root, settings=settings)

        article = load_article_file(article_path)
        segments = preprocess_article(article)
        hints = build_deterministic_hints(article, segments)

        selector_result, _ = asyncio.run(
            __import__("review_tool.agents.selector", fromlist=["run_selector"]).run_selector(
                article=article,
                segments=segments,
                hints=hints,
                registry=engine.registry,
                llm_client=engine.llm_client,
                settings=engine.settings,
            )
        )

        selector_result = validate_selector_result(
            selector_result, engine.registry, article, engine.settings
        )
        selected_ids = finalize_selected_agents(
            selector_result, article, hints, engine.registry, engine.settings,
        )

        console.print()
        console.print(f"[bold]检测稿件类型：[/bold]{selector_result.detected_article_type}")
        console.print(f"[bold]识别标签：[/bold]{', '.join(selector_result.detected_tags) or '无'}")
        console.print()

        if selector_result.selected_agents:
            console.print("[bold]Selector 选择的 Agent：[/bold]")
            for sel in selector_result.selected_agents:
                console.print(f"  - {sel.agent_id}: {sel.reason}")
        else:
            console.print("[yellow]Selector 未选择任何 Agent[/yellow]")

        console.print()
        console.print(f"[bold]最终启用 Agent（含兜底）：[/bold]{', '.join(selected_ids)}")

        if selector_result.warnings:
            for w in selector_result.warnings:
                console.print(f"[yellow]警告: {w}[/yellow]")

    except Exception as e:
        console.print(f"[red]错误: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def validate_config(
    project_root: Path = typer.Option(Path("."), "--project-root", "-r", help="项目根目录"),
):
    """校验项目配置是否合法：Agent 配置、知识库目录等。"""
    exit_code = 0

    # 检查 agents/
    agent_dir = project_root / "agents"
    if not agent_dir.exists():
        console.print("[red]错误: agents/ 目录不存在[/red]")
        raise typer.Exit(code=1)

    try:
        configs = load_agent_configs(agent_dir)
        console.print(f"[green]OK: 加载了 {len(configs)} 个 Agent 配置[/green]")
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Agent 配置错误: {e}[/red]")
        raise typer.Exit(code=1)

    # 列出 agent
    for c in configs:
        status = "enabled" if c.enabled else "disabled"
        console.print(f"  - {c.agent_id:30s} {c.name:20s} [{status}] {c.kind}")

    # 检查知识库目录
    for dir_name in ["cases", "rules", "style_guides", "risky_phrases", "examples"]:
        d = project_root / dir_name
        if d.exists():
            txt_count = len(list(d.glob("*.txt")))
            console.print(f"[green]OK: {dir_name}/ 存在 ({txt_count} 个 txt 文件)[/green]")
        else:
            console.print(f"[yellow]警告: {dir_name}/ 目录不存在[/yellow]")
            exit_code = 0  # 非致命

    # 检查 input/
    input_dir = project_root / "input"
    if not input_dir.exists():
        console.print(f"[yellow]警告: input/ 目录不存在[/yellow]")

    console.print()
    if exit_code == 0:
        console.print("[bold green]配置校验通过[/bold green]")
    else:
        console.print("[bold red]配置校验存在问题[/bold red]")

    raise typer.Exit(code=exit_code)


@app.command()
def index(
    project_root: Path = typer.Option(Path("."), "--project-root", "-r", help="项目根目录"),
):
    """重建本地知识库索引缓存。"""
    try:
        documents = load_corpus(project_root)
        console.print(f"加载文档: {len(documents)} 个")

        chunks = chunk_documents(documents)
        console.print(f"切块结果: {len(chunks)} 个 chunk")

        save_cache(project_root, chunks)
        console.print(f"[green]索引缓存已保存到 .cache/[/green]")

    except Exception as e:
        console.print(f"[red]索引失败: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def show_agents(
    project_root: Path = typer.Option(Path("."), "--project-root", "-r", help="项目根目录"),
):
    """列出所有可用 Agent。"""
    agent_dir = project_root / "agents"
    if not agent_dir.exists():
        console.print("[red]agents/ 目录不存在[/red]")
        raise typer.Exit(code=1)

    try:
        configs = load_agent_configs(agent_dir)
    except Exception as e:
        console.print(f"[red]加载失败: {e}[/red]")
        raise typer.Exit(code=1)

    table = Table(title="可用 Agent")
    table.add_column("agent_id", style="cyan")
    table.add_column("名称")
    table.add_column("状态")
    table.add_column("类型")
    table.add_column("优先级")

    for c in configs:
        status = "[green]enabled[/green]" if c.enabled else "[red]disabled[/red]"
        table.add_row(c.agent_id, c.name, status, c.kind, str(c.priority))

    console.print(table)


def main():
    app()


if __name__ == "__main__":
    main()
