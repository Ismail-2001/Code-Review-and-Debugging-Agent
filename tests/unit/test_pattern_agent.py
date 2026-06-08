"""Tests for pattern analysis agent — AST-based smell detection."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest
from agents.pattern_agent import PatternAgent
from di.container import AppContext, MetricsClient, CacheClient


@pytest.fixture
def agent():
    ctx = AppContext(config={}, cache=CacheClient(), metrics=MetricsClient())
    return PatternAgent(ctx)


@pytest.mark.asyncio
async def test_detects_long_function(agent, tmp_path):
    test_file = tmp_path / "long_func.py"
    test_file.write_text(
        "def long_func():\n" + "\n".join(f"    x = {i}" for i in range(60))
    )

    state = {"target_files": [str(test_file)], "pattern_analysis_findings": []}
    result = await agent.analyze(state)

    findings = result["pattern_analysis_findings"]
    long_funcs = [f for f in findings if f["title"] == "Long Function"]
    assert len(long_funcs) > 0
    assert long_funcs[0]["severity"] == "medium"


@pytest.mark.asyncio
async def test_detects_too_many_parameters(agent, tmp_path):
    test_file = tmp_path / "many_params.py"
    test_file.write_text("def many_params(a, b, c, d, e, f, g): pass")

    state = {"target_files": [str(test_file)], "pattern_analysis_findings": []}
    result = await agent.analyze(state)

    findings = result["pattern_analysis_findings"]
    params = [f for f in findings if f["title"] == "Too Many Parameters"]
    assert len(params) > 0
    assert params[0]["severity"] == "medium"


@pytest.mark.asyncio
async def test_detects_wildcard_imports(agent, tmp_path):
    test_file = tmp_path / "wildcard.py"
    test_file.write_text("from os import *\nfrom sys import argv\n")

    state = {"target_files": [str(test_file)], "pattern_analysis_findings": []}
    result = await agent.analyze(state)

    findings = result["pattern_analysis_findings"]
    wildcards = [f for f in findings if f["title"] == "Wildcard Import"]
    assert len(wildcards) > 0


@pytest.mark.asyncio
async def test_no_findings_for_clean_code(agent, tmp_path):
    test_file = tmp_path / "clean.py"
    test_file.write_text("def clean(a: int, b: int) -> int:\n    return a + b\n")

    state = {"target_files": [str(test_file)], "pattern_analysis_findings": []}
    result = await agent.analyze(state)

    assert len(result["pattern_analysis_findings"]) == 0
