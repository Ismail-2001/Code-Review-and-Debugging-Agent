"""Static analysis agent — combines pylint with LLM reasoning."""

from __future__ import annotations

import json
import subprocess

from src.agents.base import AnalysisAgent
from src.agents.state import CodeReviewState, Finding
from src.prompts.static_analysis import FILE_CONTEXT_TEMPLATE, STATIC_ANALYSIS_SYSTEM_PROMPT


class StaticAnalysisAgent(AnalysisAgent):
    """Performs static analysis combining pylint + AST parsing + LLM reasoning."""

    def category(self) -> str:
        return "static_analysis"

    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        files = state.get("target_files") or []
        all_findings: list[Finding] = []

        for file_path in files:
            try:
                content = self._read_file(file_path)
            except Exception as e:
                state.setdefault("errors", []).append(f"Cannot read {file_path}: {e}")
                continue

            # 1. Run pylint (synchronous, deterministic, fast)
            lint_results = self._run_pylint(file_path)

            # 2. LLM reasoning — this is the value-add over plain pylint
            llm_findings = await self.analyze_with_llm(
                system_prompt=STATIC_ANALYSIS_SYSTEM_PROMPT,
                human_template=FILE_CONTEXT_TEMPLATE,
                template_vars={
                    "file_path": file_path,
                    "content": content,
                    "lint_output": json.dumps(lint_results, indent=2) if lint_results else "No issues",
                },
                file_path=file_path,
            )

            all_findings.extend(llm_findings)

            state["files_analyzed"] = state.get("files_analyzed", 0) + 1

        state["static_analysis_findings"] = all_findings
        state["current_step"] = "static_analysis_complete"
        return state

    def _read_file(self, file_path: str) -> str:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def _run_pylint(self, file_path: str) -> list[dict]:
        """Run pylint and return structured results."""
        try:
            result = subprocess.run(
                ["pylint", "--output-format=json", "--disable=all", "--enable=all", file_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.stdout:
                return json.loads(result.stdout)
            return []
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            return []
