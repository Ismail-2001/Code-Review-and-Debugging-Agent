"""State definitions for the Code Review Agent — FAANG-grade."""

from __future__ import annotations

from typing import TypedDict, List, Dict, Optional


class Finding(TypedDict, total=False):
    """Structure for a single finding — extended for enterprise use."""
    id: str
    file: str
    line: int
    column: Optional[int]
    severity: str  # 'critical' | 'high' | 'medium' | 'low' | 'info'
    category: str  # 'bug' | 'security' | 'performance' | 'logic' | 'pattern' | 'style'
    title: str
    description: str
    impact: str
    recommendation: str
    code_snippet: Optional[str]
    suggested_fix: Optional[str]
    auto_fixable: bool
    fix_applied: bool
    dismissed: bool
    dismissed_reason: Optional[str]
    references: List[str]
    cwe_id: Optional[str]
    cvss_score: Optional[float]
    effort_minutes: Optional[int]


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def sort_by_severity(findings: list[Finding]) -> list[Finding]:
    """Sort findings by severity (critical first)."""
    return sorted(findings, key=lambda x: SEVERITY_RANK.get(x.get("severity", "info"), 5))


class CodeReviewState(TypedDict, total=False):
    """Complete state for the code review agent — designed for production."""
    repository_url: str
    local_path: str
    review_scope: str
    target_branch: Optional[str]
    target_files: Optional[List[str]]
    primary_languages: List[str]
    project_type: str
    frameworks: List[str]
    build_tools: List[str]
    repo_size_bytes: int
    config: Dict
    severity_threshold: str
    auto_fix_enabled: bool
    static_analysis_findings: List[Finding]
    pattern_analysis_findings: List[Finding]
    security_findings: List[Finding]
    performance_findings: List[Finding]
    testing_findings: List[Finding]
    logic_findings: List[Finding]
    policy_findings: List[Finding]
    all_findings: List[Finding]
    prioritized_issues: List[Finding]
    quick_wins: List[Finding]
    quality_score: float
    generated_fixes: List[Dict]
    fix_branch_name: Optional[str]
    markdown_report: str
    json_report: Dict
    html_report: str
    github_issues: List[Dict]
    messages: List[Dict]
    current_step: str
    errors: List[str]
    files_analyzed: int
    total_files: int
    analysis_start_time: float
    llm_tokens_used: int
    llm_cost_cents: float
    user_feedback: List[Dict]
    skip_categories: List[str]
