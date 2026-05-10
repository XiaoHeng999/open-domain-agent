"""CLI entry point — Typer commands + Rich formatting."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from open_agent.config import load_config

app = typer.Typer(name="agent", help="Open-domain Agent Framework CLI")
console = Console()


def _run_async(coro):
    """Run an async coroutine from sync CLI context."""
    return asyncio.run(coro)


@app.command()
def run(
    task: str = typer.Argument(..., help="Task to execute"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config YAML path"),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace directory"),
) -> None:
    """Execute a single task."""
    cfg = load_config(config, workspace=workspace)
    console.print(Panel(f"[bold]Task:[/] {task}", title="Open Agent"))

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        progress.add_task("Processing...", total=None)
        # Will be wired to Agent Runtime after it's implemented
        console.print(f"[dim]Config loaded: {cfg.model.provider}/{cfg.model.name}[/dim]")
        console.print(f"[dim]Workspace: {cfg.workspace}[/dim]")

    console.print("[green]Done.[/green]")


@app.command()
def chat(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config YAML path"),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace directory"),
) -> None:
    """Start interactive multi-turn chat."""
    cfg = load_config(config, workspace=workspace)
    console.print(Panel("[bold]Interactive Chat Mode[/bold]", title="Open Agent"))
    console.print("[dim]Type 'exit' or Ctrl+C to quit.[/dim]\n")

    while True:
        try:
            user_input = console.input("[bold cyan]You:[/] ").strip()
            if user_input.lower() in ("exit", "quit"):
                break
            if not user_input:
                continue
            console.print(f"[green]Agent:[/] (stub response) You said: {user_input}")
        except (KeyboardInterrupt, EOFError):
            break

    console.print("[dim]Goodbye.[/dim]")


@app.command(name="eval")
def eval_cmd(
    suite: str = typer.Option("smoke", "--suite", "-s", help="Eval suite name"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config YAML path"),
) -> None:
    """Run evaluation suite."""
    cfg = load_config(config)
    console.print(Panel(f"[bold]Running eval suite:[/] {suite}", title="Evaluation"))

    table = Table(title="Eval Results")
    table.add_column("Scenario", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Score", justify="right")
    table.add_column("Duration (ms)", justify="right")
    table.add_row("(no scenarios yet)", "-", "-", "-")
    console.print(table)


@app.command()
def trace(
    trace_id: str = typer.Argument(..., help="Trace ID to inspect"),
    trace_dir: str = typer.Option(".open_agent/traces", "--dir", "-d", help="Trace directory"),
) -> None:
    """View execution trace."""
    trace_path = Path(trace_dir) / f"{trace_id}.json"
    if not trace_path.exists():
        console.print(f"[red]Trace not found: {trace_id}[/red]")
        raise typer.Exit(1)

    data = json.loads(trace_path.read_text())
    console.print(Panel(json.dumps(data, indent=2, ensure_ascii=False), title=f"Trace: {trace_id}"))


@app.command(name="tool")
def tool_group(
    action: str = typer.Argument("list", help="Action: list"),
) -> None:
    """Manage tools (list registered tools)."""
    if action == "list":
        table = Table(title="Registered Tools")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Tags")
        table.add_row("(no tools registered)", "-", "-")
        console.print(table)
    else:
        console.print(f"[red]Unknown action: {action}[/red]")


@app.command(name="skill")
def skill_group(
    action: str = typer.Argument("list", help="Action: list"),
) -> None:
    """Manage skills (list available skills)."""
    if action == "list":
        table = Table(title="Available Skills")
        table.add_column("Name", style="cyan")
        table.add_column("Domain")
        table.add_column("Description")
        table.add_row("(no skills loaded)", "-", "-")
        console.print(table)
    else:
        console.print(f"[red]Unknown action: {action}[/red]")


if __name__ == "__main__":
    app()
