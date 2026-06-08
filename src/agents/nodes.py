"""Synthesis and reporting nodes — aggregate findings, prioritize, generate reports."""

from __future__ import annotations


from src.agents.state import CodeReviewState, Finding, sort_by_severity
from src.scoring.quality_score import calculate_quality_score, categorize_findings


def synthesize_findings_node(state: CodeReviewState) -> CodeReviewState:
    """Consolidate findings from all agents, deduplicate, and prioritize."""
    all_f: list[Finding] = list(state.get("static_analysis_findings", []))
    all_f.extend(state.get("pattern_analysis_findings", []))
    all_f.extend(state.get("security_findings", []))
    all_f.extend(state.get("performance_findings", []))
    all_f.extend(state.get("testing_findings", []))
    all_f.extend(state.get("logic_findings", []))
    all_f.extend(state.get("policy_findings", []))

    # Deduplicate by title (keep first occurrence)
    seen_titles: set[str] = set()
    deduped: list[Finding] = []
    for f in all_f:
        title = f.get("title", "").lower()
        if title not in seen_titles:
            seen_titles.add(title)
            deduped.append(f)

    # Prioritize by severity
    prioritized = sort_by_severity(deduped)

    # Identify quick wins
    quick_wins = [f for f in prioritized if f.get("auto_fixable")]

    # Calculate quality score
    total_files = state.get("total_files", 0) or len(state.get("target_files", [])) or 1
    quality_score = calculate_quality_score(prioritized, total_files)

    state["all_findings"] = deduped
    state["prioritized_issues"] = prioritized
    state["quick_wins"] = quick_wins[:10]
    state["quality_score"] = quality_score
    state["current_step"] = "synthesis_complete"

    return state


def should_generate_fixes(state: CodeReviewState) -> str:
    """Conditional router: should we generate fixes or skip to reporting?"""
    if not state.get("auto_fix_enabled", False):
        return "skip_fixes"

    prioritized = state.get("prioritized_issues", [])
    fixable = [f for f in prioritized if f.get("auto_fixable")]
    critical_fixable = [
        f for f in fixable
        if f.get("severity") in ("critical", "high")
    ]

    if critical_fixable:
        return "generate_fixes"
    if fixable:
        return "generate_fixes"
    return "skip_fixes"


def create_reports_node(state: CodeReviewState) -> CodeReviewState:
    """Generate markdown and JSON reports from prioritized findings."""
    from src.reporters.markdown_reporter import MarkdownReporter

    reporter = MarkdownReporter()
    prioritized = state.get("prioritized_issues", [])
    quality_score = state.get("quality_score", 100.0)
    summary = categorize_findings(prioritized)

    state["markdown_report"] = reporter.generate(
        findings=prioritized,
        quality_score=quality_score,
        summary=summary,
        repo_url=state.get("repository_url", "local"),
    )

    state["json_report"] = {
        "repository_url": state.get("repository_url", ""),
        "quality_score": quality_score,
        "summary": summary,
        "findings": prioritized,
        "generated_fixes": state.get("generated_fixes", []),
        "current_step": "reporting_complete",
        "analysis_duration_seconds": _compute_duration(state),
    }

    state["current_step"] = "reporting_complete"
    return state


def _compute_duration(state: CodeReviewState) -> float:
    start = state.get("analysis_start_time", 0)
    if not start:
        return 0.0
    import time
    return time.time() - start
