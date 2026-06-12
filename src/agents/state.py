"""State definitions for the Code Review Agent — FAANG-grade."""

from __future__ import annotations

from typing import TypedDict


class Finding(TypedDict, total=False):
    """Structure for a single finding — extended for enterprise use."""

    id: str
    file: str
    line: int
    column: int | None
    severity: str  # 'critical' | 'high' | 'medium' | 'low' | 'info'
    category: str  # 'bug' | 'security' | 'performance' | 'logic' | 'pattern' | 'style'
    title: str
    description: str
    impact: str
    recommendation: str
    code_snippet: str | None
    suggested_fix: str | None
    auto_fixable: bool
    fix_applied: bool
    dismissed: bool
    dismissed_reason: str | None
    references: list[str]
    cwe_id: str | None
    cvss_score: float | None
    effort_minutes: int | None


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def sort_by_severity(findings: list[Finding]) -> list[Finding]:
    """Sort findings by severity (critical first)."""
    return sorted(findings, key=lambda x: SEVERITY_RANK.get(x.get("severity", "info"), 5))


class CodeReviewState(TypedDict, total=False):
    """Complete state for the code review agent — designed for production."""

    repository_url: str
    local_path: str
    review_scope: str
    target_branch: str | None
    target_files: list[str] | None
    primary_languages: list[str]
    project_type: str
    frameworks: list[str]
    build_tools: list[str]
    repo_size_bytes: int
    config: dict
    severity_threshold: str
    auto_fix_enabled: bool
    static_analysis_findings: list[Finding]
    pattern_analysis_findings: list[Finding]
    security_findings: list[Finding]
    performance_findings: list[Finding]
    testing_findings: list[Finding]
    logic_findings: list[Finding]
    policy_findings: list[Finding]
    all_findings: list[Finding]
    prioritized_issues: list[Finding]
    quick_wins: list[Finding]
    quality_score: float
    generated_fixes: list[dict]
    fix_branch_name: str | None
    markdown_report: str
    json_report: dict
    html_report: str
    github_issues: list[dict]
    messages: list[dict]
    current_step: str
    errors: list[str]
    files_analyzed: int
    total_files: int
    analysis_start_time: float
    llm_tokens_used: int
    llm_cost_cents: float
    user_feedback: list[dict]
    skip_categories: list[str]
