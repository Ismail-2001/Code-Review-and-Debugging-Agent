from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from state import CodeReviewState
from agents.nodes import (
    initialize_repository,
    define_scope,
    run_static_analysis,
    run_pattern_analysis,
    run_security_audit,
    run_performance_analysis,
    assess_testing,
    verify_logic,
    synthesize_findings,
    generate_fixes,
    create_reports,
    handle_errors
)

def should_generate_fixes(state: CodeReviewState) -> str:
    """Determine if fixes should be generated."""
    if not state.get("auto_fix_enabled", False):
        return "skip_fixes"
    
    # Check if there are high/critical issues that are auto-fixable
    prioritized = state.get("prioritized_issues", [])
    critical_issues = [
        f for f in prioritized
        if f.get("severity") in ["critical", "high"] and f.get("auto_fixable", False)
    ]
    
    if critical_issues:
        return "generate_fixes"
    return "skip_fixes"

# Create the graph
workflow = StateGraph(CodeReviewState)

# Add nodes
workflow.add_node("initialization", initialize_repository)
workflow.add_node("scope_definition", define_scope)
workflow.add_node("static_analysis", run_static_analysis)
workflow.add_node("pattern_analysis", run_pattern_analysis)
workflow.add_node("security_audit", run_security_audit)
workflow.add_node("performance_analysis", run_performance_analysis)
workflow.add_node("testing_assessment", assess_testing)
workflow.add_node("logic_verification", verify_logic)
workflow.add_node("synthesis", synthesize_findings)
workflow.add_node("fix_generation", generate_fixes)
workflow.add_node("reporting", create_reports)
workflow.add_node("error_handler", handle_errors)

# Define edges
workflow.set_entry_point("initialization")

workflow.add_edge("initialization", "scope_definition")
workflow.add_edge("scope_definition", "static_analysis")
workflow.add_edge("static_analysis", "pattern_analysis")
workflow.add_edge("pattern_analysis", "security_audit")
workflow.add_edge("security_audit", "performance_analysis")
workflow.add_edge("performance_analysis", "testing_assessment")
workflow.add_edge("testing_assessment", "logic_verification")
workflow.add_edge("logic_verification", "synthesis")

# Conditional edge for fix generation
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

# Compile the graph
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
