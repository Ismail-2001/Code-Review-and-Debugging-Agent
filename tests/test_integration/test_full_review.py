import pytest
import asyncio
from agents.graph import app
import os

@pytest.mark.asyncio
async def test_full_review_flow(tmp_path):
    """Test full repository review workflow."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    
    (repo_dir / "main.py").write_text("""
def vulnerable_function(user_input):
    # This is a mock script
    return user_input

def long_function():
    # This will be long
""" + "\n".join([f"    pass" for _ in range(60)]))

    initial_state = {
        "repository_url": "local",
        "local_path": str(repo_dir),
        "review_scope": "full",
        "severity_threshold": "low",
        "auto_fix_enabled": False,
        "messages": [],
        "errors": [],
        "static_analysis_findings": [],
        "pattern_analysis_findings": [],
        "security_findings": [],
        "performance_findings": [],
        "testing_findings": [],
        "logic_findings": [],
        "files_analyzed": 0,
        "total_files": 0,
        "all_findings": [],
        "prioritized_issues": [],
        "quick_wins": [],
        "generated_fixes": [],
        "markdown_report": "",
        "json_report": {},
        "github_issues": [],
        "current_step": "started",
        "analysis_start_time": 0.0,
        "user_feedback": [],
        "skip_categories": []
    }

    config = {"configurable": {"thread_id": "test-session"}}
    
    # In a test, we might not want to wait for HITL, so we ensure fixes are disabled or scope is limited
    # But for a basic flow test, we run it and expect it to reach the reporting step (or interrupt)
    
    final_state = initial_state.copy()
    async for event in app.astream(initial_state, config):
        if isinstance(event, dict):
            for node, state_delta in event.items():
                final_state.update(state_delta)
        
    assert "reporting_complete" in final_state.get("current_step", "")
    assert len(final_state.get("all_findings", [])) >= 1
