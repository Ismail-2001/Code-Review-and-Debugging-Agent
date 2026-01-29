"""
State definitions for the Code Review Agent.
"""

from typing import TypedDict, List, Dict, Optional, Annotated
from langchain_core.messages import BaseMessage
import operator


class Finding(TypedDict):
    """Structure for a single finding."""
    id: str
    file: str
    line: int
    column: Optional[int]
    severity: str  # 'critical', 'high', 'medium', 'low', 'info'
    category: str  # 'bug', 'security', 'performance', 'style', etc.
    title: str
    description: str
    impact: str
    recommendation: str
    code_snippet: Optional[str]
    suggested_fix: Optional[str]
    auto_fixable: bool
    references: List[str]
    cwe_id: Optional[str]  # For security issues
    cvss_score: Optional[float]  # For security issues


class CodeReviewState(TypedDict):
    """
    Complete state for the code review agent.
    Uses Annotated with operator.add for list fields to accumulate values.
    """
    # Input parameters
    repository_url: str
    local_path: str
    review_scope: str
    target_branch: Optional[str]
    target_files: Optional[List[str]]
    
    # Repository metadata
    primary_languages: List[str]
    project_type: str
    frameworks: List[str]
    build_tools: List[str]
    
    # Configuration
    config: Dict
    severity_threshold: str
    auto_fix_enabled: bool
    
    # Analysis results (accumulated across nodes)
    static_analysis_findings: Annotated[List[Finding], operator.add]
    pattern_analysis_findings: Annotated[List[Finding], operator.add]
    security_findings: Annotated[List[Finding], operator.add]
    performance_findings: Annotated[List[Finding], operator.add]
    testing_findings: Annotated[List[Finding], operator.add]
    logic_findings: Annotated[List[Finding], operator.add]
    policy_findings: Annotated[List[Finding], operator.add]
    
    # Synthesized results
    all_findings: List[Finding]
    prioritized_issues: List[Finding]
    quick_wins: List[Finding]
    
    # Fix generation
    generated_fixes: List[Dict]
    fix_branch_name: Optional[str]
    
    # Reporting
    markdown_report: str
    json_report: Dict
    github_issues: List[Dict]
    
    # Conversation
    messages: Annotated[List[BaseMessage], operator.add]
    current_step: str
    errors: Annotated[List[str], operator.add]
    
    # Progress tracking
    files_analyzed: int
    total_files: int
    analysis_start_time: float
    
    # User preferences
    user_feedback: List[Dict]
    skip_categories: List[str]
