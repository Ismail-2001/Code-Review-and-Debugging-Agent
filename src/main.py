"""CodeGuardian — Main entry point. FAANG-grade CLI for cognitive code review."""

from __future__ import annotations

import asyncio
import os
import sys
import time
import json

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table




# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.di.container import create_app_context
from src.agents.graph import build_code_review_graph
from src.agents.state import CodeReviewState
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger

load_dotenv()

console = Console(emoji=False)
logger = setup_logger("codeguardian")

def safe_print(msg: str = "", style: str = ""):
    """Print safely on Windows legacy terminals."""
    try:
        if style:
            console.print(msg, style=style)
        else:
            console.print(msg)
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Strip rich markup and print plain text
        import re
        plain = re.sub(r'\[/?\w+(?: \w+=[^\]]+)*\]', '', msg)
        try:
            print(plain)
        except (UnicodeEncodeError, UnicodeDecodeError):
            print(plain.encode('ascii', errors='replace').decode())


@click.group()
def cli():
    """CodeGuardian — AI-powered cognitive code review agent."""


@cli.command()
@click.argument("repository_url")
@click.option("--scope", default="full",
              type=click.Choice(["full", "branch", "files", "diff"]),
              help="Analysis scope")
@click.option("--branch", default=None, help="Target branch for diff analysis")
@click.option("--files", default=None, help="Comma-separated file list")
@click.option("--auto-fix/--no-auto-fix", default=True, help="Enable auto-fix generation")
@click.option("--severity", default="medium",
              type=click.Choice(["critical", "high", "medium", "low", "info"]),
              help="Minimum severity threshold")
@click.option("--output", default="./reports", help="Output directory")
@click.option("--format", "output_format", default="markdown",
              type=click.Choice(["markdown", "json", "all"]),
              help="Report format")
@click.option("--config", "config_path", default=None, help="Config file path")
def review(
    repository_url: str,
    scope: str,
    branch: str | None,
    files: str | None,
    auto_fix: bool,
    severity: str,
    output: str,
    output_format: str,
    config_path: str | None,
):
    """Run a complete code review on a repository."""
    safe_print(f"[bold cyan]CodeGuardian[/bold cyan] Review: [white]{repository_url}[/white]")
    safe_print("")

    target_files = files.split(",") if files else None
    config = load_config(config_path)

    initial_state: CodeReviewState = {
        "repository_url": repository_url,
        "local_path": repository_url if os.path.isdir(repository_url) else "",
        "review_scope": scope,
        "target_branch": branch,
        "target_files": target_files,
        "severity_threshold": severity,
        "auto_fix_enabled": auto_fix,
        "config": config,
        "messages": [],
        "errors": [],
        "primary_languages": [],
        "project_type": "unknown",
        "frameworks": [],
        "build_tools": [],
        "repo_size_bytes": 0,
        "static_analysis_findings": [],
        "pattern_analysis_findings": [],
        "security_findings": [],
        "performance_findings": [],
        "testing_findings": [],
        "logic_findings": [],
        "policy_findings": [],
        "files_analyzed": 0,
        "total_files": 0,
        "all_findings": [],
        "prioritized_issues": [],
        "quick_wins": [],
        "quality_score": 100.0,
        "generated_fixes": [],
        "fix_branch_name": None,
        "markdown_report": "",
        "json_report": {},
        "html_report": "",
        "github_issues": [],
        "current_step": "started",
        "analysis_start_time": time.time(),
        "llm_tokens_used": 0,
        "llm_cost_cents": 0.0,
        "user_feedback": [],
        "skip_categories": [],
    }

    asyncio.run(_run_review(initial_state, output, output_format, config_path))


async def _run_review(
    initial_state: CodeReviewState,
    output_dir: str,
    output_format: str,
    config_path: str | None,
):
    """Execute the review pipeline with progress display."""
    ctx = create_app_context(config_path)
    graph = build_code_review_graph(ctx)

    config = {"configurable": {"thread_id": f"review-{int(time.time())}"}}

    try:
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        )
        progress.__enter__()
        task = progress.add_task("[cyan]Initializing...[/cyan]", total=None)

        try:
            final_state: CodeReviewState = initial_state.copy()
            async for event in graph.astream(initial_state, config):
                for node_name, state_delta in event.items():
                    step = state_delta.get("current_step", node_name)
                    display = step.replace("_", " ").title()
                    progress.update(task, description=f"[cyan]{display}[/cyan]")
                    final_state.update(state_delta)

            progress.update(task, description="[green]Analysis Complete![/green]")

            safe_print("")
            _display_summary(final_state)
            _save_reports(final_state, output_dir, output_format)

        except Exception as e:
            progress.update(task, description="[red]Analysis Failed[/red]")
            safe_print(f"\n[red]Error:[/red] {e}")
            logger.error("Review failed", exc_info=True)
        finally:
            try:
                progress.__exit__(None, None, None)
            except Exception:
                pass
    except Exception:
        pass


def _display_summary(state: CodeReviewState):
    """Display a rich summary table of findings."""
    findings = state.get("prioritized_issues", [])
    score = state.get("quality_score", 100.0)

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        sev = f.get("severity", "info")
        if sev in severity_counts:
            severity_counts[sev] += 1

    table = Table(title=f"CodeGuardian Results — Quality Score: {score}/100")
    table.add_column("Severity", style="bold")
    table.add_column("Count")

    for sev, count in severity_counts.items():
        table.add_row(f"{sev.capitalize()}", str(count))

    safe_print("")
    try:
        console.print(table)
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass  # skip rich table rendering on legacy terminals

    if findings:
        safe_print("\n[bold]Top Issues:[/bold]")
        for i, f in enumerate(findings[:5], 1):
            safe_print(
                f"  {i}. [{f.get('severity', 'info').upper()}] "
                f"{f.get('title', 'Untitled')} — "
                f"[dim]{f.get('file', '?')}:{f.get('line', '?')}[/dim]"
            )


def _save_reports(state: CodeReviewState, output_dir: str, output_format: str):
    """Save reports to disk."""
    os.makedirs(output_dir, exist_ok=True)

    if output_format in ("markdown", "all"):
        path = os.path.join(output_dir, "codeguardian_report.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(state.get("markdown_report", "# No report generated"))
        safe_print(f"\n[green]OK[/green] Markdown report: [blue]{path}[/blue]")

    if output_format in ("json", "all"):
        path = os.path.join(output_dir, "codeguardian_report.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state.get("json_report", {}), f, indent=2, default=str)
        safe_print(f"[green]OK[/green] JSON report: [blue]{path}[/blue]")

    # Generate GitHub Issues Summary
    if state.get("prioritized_issues"):
        path = os.path.join(output_dir, "github_issues.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(_github_issues_summary(state))
        safe_print(f"[green]OK[/green] GitHub Issues summary: [blue]{path}[/blue]")

    safe_print("\n[bold green]Review complete![/bold green]")


def _github_issues_summary(state: CodeReviewState) -> str:
    """Generate a GitHub Issues-friendly summary."""
    lines = ["# CodeGuardian Issues\n"]
    for i, f in enumerate(state.get("prioritized_issues", [])[:20], 1):
        sev = f.get("severity", "info").upper()
        title = f.get("title", "Untitled")
        file = f.get("file", "?")
        line = f.get("line", "?")
        lines.append(f"### {i}. [{sev}] {title}")
        lines.append(f"- **Location**: `{file}:{line}`")
        lines.append(f"- **Description**: {f.get('description', '')}")
        lines.append(f"- **Recommendation**: {f.get('recommendation', '')}")
        lines.append("")
    return "\n".join(lines)


@cli.command()
def version():
    """Show version information."""
    safe_print("[bold]CodeGuardian v2.0.0[/bold]")
    safe_print("FAANG-grade cognitive code review agent")
    safe_print("Powered by LangGraph + LLMs")


if __name__ == "__main__":
    cli()
