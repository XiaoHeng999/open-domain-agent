"""CLI entry point — Typer commands + Rich formatting."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from prompt_toolkit import prompt as _ptk_prompt
from prompt_toolkit.shortcuts import PromptSession
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from open_agent.config_loader import load_config

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
    from open_agent.runtime import AgentRuntime

    cfg = load_config(config, workspace=workspace)
    console.print(Panel(f"[bold]Task:[/] {task}", title="Open Agent"))
    console.print(f"[dim]Config: {cfg.model.provider}/{cfg.model.name}[/dim]")
    console.print(f"[dim]Workspace: {cfg.workspace}[/dim]\n")

    runtime = AgentRuntime(config=cfg)

    async def _run():
        await runtime.on_start()
        try:
            return await runtime.run(task)
        finally:
            await runtime.on_stop()

    try:
        response = _run_async(_run())
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)

    # Display agent loop steps
    for i, step_info in enumerate(response.metadata.get("steps", [])):
        console.print(f"[bold cyan]Step {i + 1}:[/]")
        if step_info.get("thought"):
            console.print(f"  [yellow]Thought:[/] {step_info['thought']}")
        if step_info.get("action"):
            console.print(f"  [blue]Action:[/] {step_info['action']}")
        if step_info.get("observation"):
            console.print(f"  [green]Observation:[/] {step_info['observation']}")

    console.print(f"\n[bold green]Answer:[/] {response.output}")
    console.print(
        f"[dim]Trace: {response.trace_id} | "
        f"Steps: {response.metadata.get('total_steps', '?')} | "
        f"Duration: {response.duration_ms:.0f}ms[/dim]"
    )


@app.command()
def chat(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config YAML path"),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace directory"),
) -> None:
    """Start interactive multi-turn chat."""
    from open_agent.runtime import AgentRuntime

    cfg = load_config(config, workspace=workspace)
    console.print(Panel("[bold]Interactive Chat Mode[/bold]", title="Open Agent"))
    console.print(f"[dim]Config: {cfg.model.provider}/{cfg.model.name}[/dim]")
    console.print("[dim]Type 'exit' or Ctrl+C to quit.[/dim]\n")

    runtime = AgentRuntime(config=cfg)

    async def _run():
        await runtime.on_start()
        session: PromptSession[str] = PromptSession()
        try:
            while True:
                try:
                    user_input = (await session.prompt_async(
                        "\033[1;36myour prompt:\033[0m ",
                    )).strip()
                except (KeyboardInterrupt, EOFError):
                    break
                if user_input.lower() in ("exit", "quit"):
                    break
                if not user_input:
                    continue

                try:
                    response = await runtime.run(user_input)

                    # Routing summary
                    if response.routing:
                        rd = response.routing
                        console.print(
                            f"[dim]🔧 Routing → "
                            f"complexity={rd.complexity.complexity} "
                            f"domain={rd.domain.domain} "
                            f"intent={rd.intent.intent} "
                            f"method={rd.method}[/dim]"
                        )

                    # Display steps
                    for i, step_info in enumerate(response.metadata.get("steps", [])):
                        console.print(f"[bold cyan]Step {i + 1}:[/]")
                        if step_info.get("thought"):
                            console.print(f"  [yellow]Thought:[/] {step_info['thought']}")
                        if step_info.get("action"):
                            console.print(f"  [blue]Action:[/] {step_info['action']}")
                        if step_info.get("observation"):
                            obs_text = step_info['observation']
                            preview = obs_text[:200] + "..." if len(obs_text) > 200 else obs_text
                            console.print(f"  [green]Observation:[/] {preview}")

                    console.print(f"\n[bold green]Answer:[/] {response.output}")
                    console.print(
                        f"[dim]📊 Trace: {response.trace_id} | "
                        f"Steps: {response.metadata.get('total_steps', '?')} | "
                        f"Duration: {response.duration_ms:.0f}ms[/dim]\n"
                    )
                except Exception as exc:
                    console.print(f"[red]Error: {exc}[/red]\n")
        finally:
            await runtime.on_stop()

    try:
        _run_async(_run())
    except KeyboardInterrupt:
        pass
    console.print("[dim]Goodbye.[/dim]")


@app.command(name="eval")
def eval_cmd(
    suite: str = typer.Option("smoke", "--suite", "-s", help="Eval suite name"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config YAML path"),
    scenarios_dir: Optional[str] = typer.Option(None, "--dir", "-d", help="Scenarios directory"),
    no_runtime: bool = typer.Option(False, "--no-runtime", help="Only load scenarios without running"),
) -> None:
    """Run evaluation suite."""
    from open_agent.eval.runner import EvalRunner

    cfg = load_config(config)
    console.print(Panel(f"[bold]Running eval suite:[/] {suite}", title="Evaluation"))

    scenarios_path = Path(scenarios_dir) if scenarios_dir else Path("evals")
    runner = EvalRunner(scenarios_dir=scenarios_path)

    scenarios = runner.load_suite(suite)
    if not scenarios:
        console.print(f"[yellow]No scenarios found in {scenarios_path / suite}[/yellow]")
        return

    console.print(f"[dim]Loaded {len(scenarios)} scenario(s)[/dim]\n")

    # --no-runtime: just display loaded scenarios
    if no_runtime:
        table = Table(title="Scenarios")
        table.add_column("Name", style="cyan")
        table.add_column("Input")
        for s in scenarios:
            table.add_row(s["name"], s["input"][:60])
        console.print(table)
        return

    # Try to create AgentRuntime for real execution
    runtime = None
    try:
        from open_agent.runtime import AgentRuntime
        runtime = AgentRuntime(config=cfg)
    except Exception:
        pass

    if runtime is not None:
        runner._runtime = runtime

    async def _run():
        if runtime is not None:
            await runtime.on_start()
            try:
                return await runner.run_suite(suite)
            finally:
                await runtime.on_stop()
        else:
            return await runner.run_suite(suite)

    try:
        results = _run_async(_run())
    except NotImplementedError:
        console.print("[yellow]Runtime not configured — showing loaded scenarios only.[/yellow]")
        table = Table(title="Scenarios")
        table.add_column("Name", style="cyan")
        table.add_column("Input")
        for s in scenarios:
            table.add_row(s["name"], s["input"][:60])
        console.print(table)
        return
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)

    table = Table(title="Eval Results")
    table.add_column("Scenario", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    passed = 0
    failed = 0
    for r in results:
        status = r["status"]
        if status == "pass":
            passed += 1
            style = "green"
        else:
            failed += 1
            style = "red"
        details = "; ".join(
            f"{c['type']}: {'ok' if c['passed'] else 'FAIL'}"
            for c in r.get("checks", [])
        )
        table.add_row(r["name"], f"[{style}]{status}[/{style}]", details)

    console.print(table)
    console.print(f"\n[bold]Summary:[/] {passed} passed, {failed} failed, {len(results)} total")


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
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config YAML path"),
) -> None:
    """Manage tools (list registered tools)."""
    if action == "list":
        from open_agent.registry import ToolRegistry
        from open_agent.config import load_config as load_agent_config

        cfg = load_agent_config(config)
        registry = ToolRegistry()
        from open_agent.registry import scan_builtin_tools
        scan_builtin_tools(registry, cfg)

        # Register SearchTool (only needs workspace, always available)
        from open_agent.tools.search import SearchTool
        if not registry.has("search"):
            registry.register(SearchTool(workspace=cfg.workspace))

        # Show placeholders for runtime-dependent tools
        from open_agent.tools.self import SelfTool
        from open_agent.tools.sandbox_control import SandboxControlTool
        from open_agent.tools.mcp_client import MCPClientTool
        if not registry.has("self"):
            registry.register(SelfTool(react_loop=None, runtime=None))
        if not registry.has("sandbox_control"):
            registry.register(SandboxControlTool(sandbox=None))
        if not registry.has("mcp_client"):
            registry.register(MCPClientTool(mcp_manager=None))

        table = Table(title="Registered Tools")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Read-only")
        table.add_column("Safety")

        for tool in registry.list_tools():
            table.add_row(
                tool.name,
                tool.description[:60] + ("..." if len(tool.description) > 60 else ""),
                "Yes" if tool.read_only else "No",
                ", ".join(tool.safety_checks) if tool.safety_checks else "-",
            )

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
