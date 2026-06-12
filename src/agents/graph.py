"""LangGraph graph definition — orchestrates the entire review pipeline."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agents.state import CodeReviewState
from src.di.container import AppContext, create_app_context


def build_code_review_graph(ctx: AppContext) -> StateGraph:
    """Build the complete code review graph with all nodes.

    The graph supports:
    - Sequential agent execution
    - Conditional routing for fix generation (Human-in-the-Loop)
    - Checkpoint-based state persistence
    - Interrupt points for HITL approval
    """
    from src.agents.fix_agent import FixAgent
    from src.agents.logic_agent import LogicAgent
    from src.agents.nodes import (
        create_reports_node,
        should_generate_fixes,
        synthesize_findings_node,
    )
    from src.agents.pattern_agent import PatternAgent
    from src.agents.performance_agent import PerformanceAgent
    from src.agents.security_agent import SecurityAgent
    from src.agents.static_analysis_agent import StaticAnalysisAgent
    from src.agents.testing_agent import TestingAgent
    from src.rag.policy_engine import PolicyVerificationAgent

    # Instantiate agents with DI context
    agents = {
        "static_analysis": StaticAnalysisAgent(ctx),
        "pattern_analysis": PatternAgent(ctx),
        "security_audit": SecurityAgent(ctx),
        "performance_analysis": PerformanceAgent(ctx),
        "testing_assessment": TestingAgent(ctx),
        "logic_verification": LogicAgent(ctx),
        "policy_verification": PolicyVerificationAgent(ctx),
        "fix_generation": FixAgent(ctx),
    }

    workflow = StateGraph(CodeReviewState)

    # Add agent nodes
    for name, agent in agents.items():
        workflow.add_node(name, agent)

    # Add synthesis and reporting nodes
    workflow.add_node("synthesis", synthesize_findings_node)
    workflow.add_node("reporting", create_reports_node)

    # Define the pipeline edges
    config = ctx.config
    enabled_checks = config.get("enabled_checks", list(agents.keys()))

    # Set entry point
    workflow.set_entry_point("static_analysis")

    # Build sequential chain from enabled checks
    ordered_pipeline = [
        "static_analysis",
        "pattern_analysis",
        "security_audit",
        "performance_analysis",
        "testing_assessment",
        "logic_verification",
        "policy_verification",
    ]

    prev_node = None
    for node in ordered_pipeline:
        if node in enabled_checks and node in dict(workflow.nodes):
            if prev_node:
                workflow.add_edge(prev_node, node)
            prev_node = node

    # Always end at synthesis
    if prev_node and prev_node in workflow.nodes:
        workflow.add_edge(prev_node, "synthesis")
    else:
        workflow.set_entry_point("synthesis")

    # Conditional edge for fix generation
    if "fix_generation" in dict(workflow.nodes):
        workflow.add_conditional_edges(
            "synthesis",
            should_generate_fixes,
            {
                "generate_fixes": "fix_generation",
                "skip_fixes": "reporting",
            },
        )
        workflow.add_edge("fix_generation", "reporting")
    else:
        workflow.add_edge("synthesis", "reporting")

    workflow.add_edge("reporting", END)

    # Compile with checkpointing for HITL support
    return workflow.compile(  # type: ignore[return-value]
        checkpointer=ctx.checkpointer,  # type: ignore[arg-type]
        interrupt_before=["fix_generation"] if "fix_generation" in dict(workflow.nodes) else [],
    )


def create_default_graph() -> StateGraph:
    """Create a graph with default configuration."""
    ctx = create_app_context()
    return build_code_review_graph(ctx)
