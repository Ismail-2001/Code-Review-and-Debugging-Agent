from typing import TypedDict, List, Dict, Optional, Annotated
from langchain_core.messages import BaseMessage
import operator

class CodeReviewState(TypedDict):
    """
    Complete state for the code review agent.
    Each field is preserved across state transitions.
    """
    # Input parameters
    repository_url: str
    local_path: str
    review_scope: str  # 'full', 'branch', 'files', 'diff'
    target_branch: Optional[str]
    target_files: Optional[List[str]]
    
    # Repository metadata
    primary_languages: List[str]
    project_type: str  # 'web', 'cli', 'library', 'mobile', etc.
    frameworks: List[str]
    build_tools: List[str]
    
    # Configuration
    config: Dict  # From .codeguardian.yml or defaults
    severity_threshold: str  # 'critical', 'high', 'medium', 'low', 'info'
    auto_fix_enabled: bool
    
    # Analysis results (accumulated)
    static_analysis_findings: Annotated[List[Dict], operator.add]
    pattern_analysis_findings: Annotated[List[Dict], operator.add]
    security_findings: Annotated[List[Dict], operator.add]
    performance_findings: Annotated[List[Dict], operator.add]
    testing_findings: Annotated[List[Dict], operator.add]
    logic_findings: Annotated[List[Dict], operator.add]
    
    # Synthesized results
    all_findings: List[Dict]
    prioritized_issues: List[Dict]
    quick_wins: List[Dict]
    
    # Fix generation
    generated_fixes: List[Dict]
    fix_branch_name: Optional[str]
    
    # Reporting
    markdown_report: str
    json_report: Dict
    github_issues: List[Dict]
    
    # Conversation and iteration
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
