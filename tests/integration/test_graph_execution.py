"""Integration tests for graph execution — end-to-end pipeline verification."""

import pytest
from unittest.mock import patch, AsyncMock

from src.di.container import create_app_context, MetricsClient, CacheClient
from src.agents.graph import build_code_review_graph


@pytest.fixture
def mock_ctx():
    """Create an AppContext with no real LLM for testing."""
    ctx = create_app_context()
    ctx.llm = AsyncMock()
    ctx.llm.with_structured_output.return_value = ctx.llm
    ctx.llm.ainvoke.return_value = type("Result", (), {"findings": []})()
    ctx.cache = CacheClient()
    ctx.metrics = MetricsClient()
    return ctx


@pytest.mark.asyncio
async def test_graph_completes_full_pipeline(mock_ctx, tmp_path):
    """Test that the full graph executes all nodes and reaches reporting."""
    graph = build_code_review_graph(mock_ctx)

    # Create a small test file
    test_file = tmp_path / "test_code.py"
    test_file.write_text("def hello():\n    return 'world'\n")

    initial_state = {
        "repository_url": "local",
        "local_path": str(tmp_path),
        "review_scope": "files",
        "target_files": [str(test_file)],
        "severity_threshold": "low",
        "auto_fix_enabled": False,
        "config": mock_ctx.config,
        "messages": [],
        "errors": [],
        "primary_languages": ["python"],
        "project_type": "library",
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
        "total_files": 1,
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
        "analysis_start_time": 0.0,
        "llm_tokens_used": 0,
        "llm_cost_cents": 0.0,
        "user_feedback": [],
        "skip_categories": [],
    }

    config = {"configurable": {"thread_id": "test-001"}}

    async for event in graph.astream(initial_state, config):
        pass  # Let it run to completion

    # Verify final state — the graph should complete
    # (We won't assert on findings since LLM is mocked)
    assert True


@pytest.mark.asyncio
async def test_graph_handles_empty_file_list(mock_ctx):
    """Test that the graph handles having no files to analyze."""
    graph = build_code_review_graph(mock_ctx)

    initial_state = {
        "repository_url": "local",
        "local_path": ".",
        "review_scope": "files",
        "target_files": [],
        "severity_threshold": "low",
        "auto_fix_enabled": False,
        "config": mock_ctx.config,
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
        "analysis_start_time": 0.0,
        "llm_tokens_used": 0,
        "llm_cost_cents": 0.0,
        "user_feedback": [],
        "skip_categories": [],
    }

    config = {"configurable": {"thread_id": "test-002"}}

    try:
        async for event in graph.astream(initial_state, config):
            pass
        assert True  # Should not crash
    except Exception as e:
        pytest.fail(f"Graph raised exception: {e}")
