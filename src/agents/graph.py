from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents.state import CodeReviewState
import operator

# Node functions
def initialize_repository_node(state: CodeReviewState) -> CodeReviewState:
    state["current_step"] = "initializing_repository"
    return state

def define_scope_node(state: CodeReviewState) -> CodeReviewState:
    state["current_step"] = "defining_scope"
    return state

def run_static_analysis_node(state: CodeReviewState) -> CodeReviewState:
    state["current_step"] = "running_static_analysis"
    return state

def run_pattern_analysis_node(state: CodeReviewState) -> CodeReviewState:
    state["current_step"] = "running_pattern_analysis"
    return state

def run_security_audit_node(state: CodeReviewState) -> CodeReviewState:
    state["current_step"] = "running_security_audit"
    return state

def run_performance_analysis_node(state: CodeReviewState) -> CodeReviewState:
    state["current_step"] = "running_performance_analysis"
    return state

def assess_testing_node(state: CodeReviewState) -> CodeReviewState:
    state["current_step"] = "assessing_testing"
    return state

def verify_logic_node(state: CodeReviewState) -> CodeReviewState:
    state["current_step"] = "verifying_logic"
    return state

def verify_policy_node(state: CodeReviewState) -> CodeReviewState:
    state["current_step"] = "verifying_policy"
    return state

def synthesize_findings_node(state: CodeReviewState) -> CodeReviewState:
    state["current_step"] = "synthesizing_findings"
    # Consolidate findings
    all_f = (state.get("static_analysis_findings", []) + 
             state.get("pattern_analysis_findings", []) + 
             state.get("security_findings", []) +
             state.get("performance_findings", []) +
             state.get("testing_findings", []) +
             state.get("logic_findings", []) +
             state.get("policy_findings", []))
    state["all_findings"] = all_f
    state["prioritized_issues"] = sorted(all_f, key=lambda x: x.get("severity", "info"))
    return state

def generate_fixes_node(state: CodeReviewState) -> CodeReviewState:
    state["current_step"] = "generating_fixes"
    return state

def create_reports_node(state: CodeReviewState) -> CodeReviewState:
    state["current_step"] = "creating_reports"
    state["markdown_report"] = "# Code Review Report\nGenerated report content."
    return state

def should_generate_fixes(state: CodeReviewState) -> str:
    """Determine if fixes should be generated."""
    if not state.get("auto_fix_enabled", False):
        return "skip_fixes"
    return "generate_fixes"

# Create the graph
def create_code_review_graph():
    workflow = StateGraph(CodeReviewState)

    # Add Nodes
    workflow.add_node("initialization", initialize_repository_node)
    workflow.add_node("scope_definition", define_scope_node)
    workflow.add_node("static_analysis", run_static_analysis_node)
    workflow.add_node("pattern_analysis", run_pattern_analysis_node)
    workflow.add_node("security_audit", run_security_audit_node)
    workflow.add_node("performance_analysis", run_performance_analysis_node)
    workflow.add_node("testing_assessment", assess_testing_node)
    workflow.add_node("logic_verification", verify_logic_node)
    workflow.add_node("policy_verification", verify_policy_node)
    workflow.add_node("synthesis", synthesize_findings_node)
    workflow.add_node("fix_generation", generate_fixes_node)
    workflow.add_node("reporting", create_reports_node)

    # Set Edges
    workflow.set_entry_point("initialization")
    workflow.add_edge("initialization", "scope_definition")
    workflow.add_edge("scope_definition", "static_analysis")
    workflow.add_edge("static_analysis", "pattern_analysis")
    workflow.add_edge("pattern_analysis", "security_audit")
    workflow.add_edge("security_audit", "performance_analysis")
    workflow.add_edge("performance_analysis", "testing_assessment")
    workflow.add_edge("testing_assessment", "logic_verification")
    workflow.add_edge("logic_verification", "policy_verification")
    workflow.add_edge("policy_verification", "synthesis")
    
    # Conditional edge for fixes with human-in-the-loop approval
    workflow.add_conditional_edges(
        "synthesis",
        should_generate_fixes,
        {
            "generate_fixes": "fix_generation",
            "skip_fixes": "reporting"
        }
    )
    workflow.add_edge("fix_generation", "reporting")
    workflow.add_edge("reporting", END)

    # Compile with checkpointer for HITL
    memory = MemorySaver()
    return workflow.compile(
        checkpointer=memory,
        interrupt_before=["fix_generation"]  # Wait for user approval
    )

app = create_code_review_graph()
