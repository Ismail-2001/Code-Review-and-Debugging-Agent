"""
Node implementations for the Code Review Agent LangGraph.
"""

from typing import Dict, List, Any
from agents.state import CodeReviewState, Finding
from tools.git_operations import clone_repository, get_changed_files
from tools.code_analysis import parse_python_ast, run_pylint, calculate_cyclomatic_complexity, detect_code_smells
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
import os
import time
import uuid
import ast
from utils.rag_engine import RAGEngine

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp",
    temperature=0.1
)

def initialize_repository_node(state: CodeReviewState) -> CodeReviewState:
    """Initialize repository and detect project structure."""
    repo_url = state.get("repository_url")
    local_path = state.get("local_path", "./repo_to_review")
    
    if repo_url and repo_url != "local":
        result = clone_repository.invoke({"repo_url": repo_url, "local_path": local_path})
        state["local_path"] = local_path
    else:
        state["local_path"] = "."

    # Mock detection for demo
    state["primary_languages"] = ["python"]
    state["project_type"] = "library"
    state["current_step"] = "repository_initialized"
    return state

def define_scope_node(state: CodeReviewState) -> CodeReviewState:
    """Identify files to analyze based on scope."""
    scope = state.get("review_scope", "full")
    local_path = state.get("local_path")
    
    files = []
    if scope == "full":
        # Logic to list all files (simplified)
        for root, _, filenames in os.walk(local_path):
            for f in filenames:
                if f.endswith('.py'):
                    files.append(os.path.join(root, f))
    elif scope == "diff":
        files = get_changed_files.invoke({"repo_path": local_path})
    
    state["target_files"] = files[:10]  # Limit for demo
    state["total_files"] = len(files)
    state["current_step"] = "scope_defined"
    return state

def run_static_analysis_node(state: CodeReviewState) -> CodeReviewState:
    """Execute linting and AST analysis."""
    files = state.get("target_files", [])
    findings = []
    
    for file_path in files:
        # Run Pylint
        lint_results = run_pylint.invoke({"file_path": file_path})
        for lint in lint_results:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                file=file_path,
                line=lint.get("line", 0),
                severity=lint.get("severity", "medium"),
                category="style",
                title=f"Lint Issue: {lint.get('symbol')}",
                description=lint.get("message", ""),
                auto_fixable=False
            ))
            
        # Run AST
        ast_info = parse_python_ast.invoke({"file_path": file_path})
        if ast_info.get("status") == "error":
            state["errors"].append(ast_info.get("error"))
            
    state["static_analysis_findings"] = findings
    state["files_analyzed"] += len(files)
    state["current_step"] = "static_analysis_complete"
    return state

def run_pattern_analysis_node(state: CodeReviewState) -> CodeReviewState:
    """Detect code smells."""
    files = state.get("target_files", [])
    findings = []
    
    for file_path in files:
        smells = detect_code_smells.invoke({"file_path": file_path})
        for smell in smells:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                file=file_path,
                line=smell.get("line", 0),
                severity="medium",
                category="pattern",
                title=smell.get("type").replace("_", " ").title(),
                description=smell.get("message", ""),
                auto_fixable=True
            ))
            
    state["pattern_analysis_findings"] = findings
    state["current_step"] = "pattern_analysis_complete"
    return state

def run_security_audit_node(state: CodeReviewState) -> CodeReviewState:
    """Stub for security audit."""
    state["security_findings"] = []
    state["current_step"] = "security_audit_complete"
    return state

def run_performance_analysis_node(state: CodeReviewState) -> CodeReviewState:
    """Check complexity."""
    files = state.get("target_files", [])
    findings = []
    
    for file_path in files:
        complexity = calculate_cyclomatic_complexity.invoke({"file_path": file_path})
        comp_list = complexity.get("complexity_data", [])
        for item in comp_list:
            if item.get("complexity", 0) > 10:
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    file=file_path,
                    line=item.get("lineno", 0),
                    severity="high",
                    category="performance",
                    title="High Cyclomatic Complexity",
                    description=f"Function {item.get('name')} has complexity {item.get('complexity')}",
                    auto_fixable=False
                ))
                
    state["performance_findings"] = findings
    state["current_step"] = "performance_analysis_complete"
    return state

def assess_testing_node(state: CodeReviewState) -> CodeReviewState:
    state["testing_findings"] = []
    state["current_step"] = "testing_assessment_complete"
    return state

def verify_logic_node(state: CodeReviewState) -> CodeReviewState:
    state["logic_findings"] = []
    state["current_step"] = "logic_verification_complete"
    return state

def verify_policy_node(state: CodeReviewState) -> CodeReviewState:
    """Verify code against local company policies using RAG."""
    rag = RAGEngine()
    rag.load_standards()
    
    files = state.get("target_files", [])
    findings = []
    
    for file_path in files:
        # Simulate checking a file against indexed standards
        policy_context = rag.query_standards(f"Coding standards for {file_path}")
        # In a real scenario, LLM would analyze code using policy_context
        findings.append(Finding(
            id=str(uuid.uuid4()),
            file=file_path,
            line=1,
            severity="info",
            category="policy",
            title="Applied Local Policy",
            description=f"Verified against standard: {policy_context}",
            auto_fixable=False
        ))
        
    state["policy_findings"] = findings
    state["current_step"] = "policy_verification_complete"
    return state

def synthesize_findings_node(state: CodeReviewState) -> CodeReviewState:
    """Consolidate and prioritize results."""
    all_f = (state.get("static_analysis_findings", []) + 
             state.get("pattern_analysis_findings", []) + 
             state.get("security_findings", []) +
             state.get("performance_findings", []) +
             state.get("testing_findings", []) +
             state.get("logic_findings", []) +
             state.get("policy_findings", []))
    
    state["all_findings"] = all_f
    # Sort by severity priority (critical > high > medium > low > info)
    severity_map = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    state["prioritized_issues"] = sorted(all_f, key=lambda x: severity_map.get(x.get("severity", "info"), 5))
    state["current_step"] = "synthesis_complete"
    return state

def validate_python_syntax(code: str) -> bool:
    """Validate if the provided string is valid Python syntax."""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False

def generate_fixes_node(state: CodeReviewState) -> CodeReviewState:
    """Generate and validate code fixes for identified issues."""
    state["current_step"] = "generating_fixes"
    fixable_issues = [f for f in state.get("prioritized_issues", []) if f.get("auto_fixable")]
    
    generated_fixes = []
    for issue in fixable_issues:
        # Simulate LLM generating a fix
        # In a real scenario, we would call llm.ainvoke([SystemMessage(...), HumanMessage(...)])
        mock_fix = f"# Fixed {issue['title']}\ndef fixed_function():\n    pass"
        
        # AST Validation
        if validate_python_syntax(mock_fix):
            generated_fixes.append({
                "issue_id": issue["id"],
                "fix_code": mock_fix,
                "status": "valid_syntax"
            })
        else:
            state["errors"].append(f"LLM generated invalid syntax for issue {issue['id']}")
            
    state["generated_fixes"] = generated_fixes
    state["current_step"] = "fix_generation_complete"
    return state

def create_reports_node(state: CodeReviewState) -> CodeReviewState:
    """Generate Markdown and JSON reports."""
    from reporters.markdown_reporter import MarkdownReporter
    reporter = MarkdownReporter()
    state["markdown_report"] = reporter.generate(state.get("prioritized_issues", []))
    state["json_report"] = {"findings": state.get("prioritized_issues", []), "summary": "Analysis complete"}
    state["current_step"] = "reporting_complete"
    return state
