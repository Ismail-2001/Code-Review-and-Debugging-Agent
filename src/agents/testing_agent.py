"""Testing assessment agent — evaluates test coverage and quality."""

from __future__ import annotations

import os
import subprocess
import uuid

from src.agents.base import AnalysisAgent
from src.agents.state import CodeReviewState, Finding


class TestingAgent(AnalysisAgent):
    """Analyzes test coverage and test quality."""

    def category(self) -> str:
        return "testing_assessment"

    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        local_path = state.get("local_path", ".")
        findings: list[Finding] = []

        # 1. Find test files
        test_files = self._find_test_files(local_path)

        # 2. Run test coverage if pytest is configured
        coverage_data = self._run_coverage(local_path)

        source_files = state.get("target_files", [])

        # 3. Identify untested source files
        tested_files = set()
        if coverage_data:
            for item in coverage_data:
                tested_files.add(item.get("filename", ""))

        for src_file in source_files:
            rel_path = os.path.relpath(src_file, local_path)
            if rel_path not in tested_files:
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    file=src_file,
                    line=1,
                    severity="medium",
                    category="testing",
                    title="No Test Coverage",
                    description=f"File '{rel_path}' has no test coverage detected. "
                                f"No tests exercise this code.",
                    recommendation=f"Add unit tests for '{rel_path}'. Aim for >80% coverage.",
                    auto_fixable=False,
                ))

        # 4. Check test-to-source ratio
        if source_files and test_files:
            ratio = len(test_files) / len(source_files)
            if ratio < 0.3:
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    file=".",
                    line=1,
                    severity="high",
                    category="testing",
                    title="Low Test-to-Source Ratio",
                    description=f"Only {len(test_files)} test files for "
                                f"{len(source_files)} source files ({ratio:.0%}). "
                                f"Aim for at least 30%.",
                    recommendation="Add more test files. Consider one test file per source file.",
                    auto_fixable=False,
                ))

        state["testing_findings"] = findings
        state["current_step"] = "testing_assessment_complete"
        return state

    def _find_test_files(self, path: str) -> list[str]:
        test_files = []
        for root, _, files in os.walk(path):
            if "node_modules" in root or ".git" in root or "__pycache__" in root:
                continue
            for f in files:
                if f.startswith("test_") and f.endswith(".py"):
                    test_files.append(os.path.join(root, f))
        return test_files

    def _run_coverage(self, path: str) -> list[dict]:
        try:
            result = subprocess.run(
                ["coverage", "json", "--pretty"],
                capture_output=True, text=True, timeout=30, cwd=path,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                return data.get("files", {}).values()
            return []
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return []
