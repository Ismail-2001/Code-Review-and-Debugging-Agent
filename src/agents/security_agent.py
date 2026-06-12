"""Security audit agent — combines bandit + semgrep + LLM reasoning."""

from __future__ import annotations

import asyncio
import json
import subprocess
import uuid

from src.agents.base import AnalysisAgent
from src.agents.state import CodeReviewState, Finding
from src.prompts.security import SECURITY_SYSTEM_PROMPT

SECURITY_TEMPLATE = """File: {file_path}

```python
{content}
```
"""


class SecurityAgent(AnalysisAgent):
    """Performs security audit: bandit + semgrep + LLM for advanced vuln detection."""

    def category(self) -> str:
        return "security_audit"

    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        files = state.get("target_files") or []
        all_findings: list[Finding] = []
        errors: list[str] = []

        async def analyze_file(file_path: str) -> tuple[list[Finding], list[str]]:
            findings = []
            file_errors = []

            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                return [], [f"Cannot read {file_path}: {e}"]

            # 1. Bandit scan (fast, deterministic)
            bandit_findings, bandit_errors = await self._run_bandit(file_path)
            findings.extend(bandit_findings)
            file_errors.extend(bandit_errors)

            # 2. Semgrep scan (rule-based SAST)
            semgrep_findings, semgrep_errors = await self._run_semgrep(file_path)
            findings.extend(semgrep_findings)
            file_errors.extend(semgrep_errors)

            # 3. LLM reasoning for semantic security issues that tools miss
            llm_findings = await self.analyze_with_llm(
                system_prompt=SECURITY_SYSTEM_PROMPT,
                human_template=SECURITY_TEMPLATE,
                template_vars={"file_path": file_path, "content": content},
                file_path=file_path,
            )

            # Deduplicate: if bandit/semgrep already found it, skip LLM duplicate
            tool_titles = {f["title"].lower() for f in findings}
            for lf in llm_findings:
                if lf["title"].lower() not in tool_titles:
                    findings.append(lf)

            return findings, file_errors

        # Parallel file analysis
        results = await asyncio.gather(
            *[analyze_file(f) for f in files],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, Exception):
                errors.append(f"Security analysis error: {result}")
            elif isinstance(result, tuple):
                file_findings, file_errors = result
                all_findings.extend(file_findings)
                errors.extend(file_errors)

        state["security_findings"] = all_findings
        state["errors"] = state.get("errors", []) + errors
        state["current_step"] = "security_audit_complete"
        return state

    async def _run_bandit(self, file_path: str) -> tuple[list[Finding], list[str]]:
        try:
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: subprocess.run(
                        ["bandit", "-f", "json", "-q", file_path],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    ),
                ),
                timeout=35,
            )
            if not result.stdout:
                return [], []

            data = json.loads(result.stdout)
            findings = []
            for issue in data.get("results", []):
                severity = issue.get("issue_severity", "medium").lower()
                severity_map = {"low": "low", "medium": "medium", "high": "high"}
                findings.append(
                    Finding(
                        id=str(uuid.uuid4()),
                        file=file_path,
                        line=issue.get("line_number", 0),
                        severity=severity_map.get(severity, "medium"),
                        category="security",
                        title=f"Bandit: {issue.get('test_name', 'Unknown')}",
                        description=issue.get("issue_text", ""),
                        recommendation=issue.get("more_info", ""),
                        auto_fixable=False,
                    )
                )
            return findings, []
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return [], [f"Bandit failed for {file_path}: {e}"]
        except json.JSONDecodeError:
            return [], []

    async def _run_semgrep(self, file_path: str) -> tuple[list[Finding], list[str]]:
        try:
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: subprocess.run(
                        ["semgrep", "--json", "--config", "auto", "--optimizations", "all", file_path],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    ),
                ),
                timeout=65,
            )
            if not result.stdout:
                return [], []

            data = json.loads(result.stdout)
            findings = []
            for result_item in data.get("results", []):
                severity = result_item.get("extra", {}).get("severity", "WARNING")
                severity_map = {"INFO": "low", "WARNING": "medium", "ERROR": "high"}
                findings.append(
                    Finding(
                        id=str(uuid.uuid4()),
                        file=file_path,
                        line=result_item.get("start", {}).get("line", 0),
                        severity=severity_map.get(severity, "medium"),
                        category="security",
                        title=f"Semgrep: {result_item.get('check_id', 'Unknown')}",
                        description=result_item.get("extra", {}).get("message", ""),
                        recommendation=result_item.get("extra", {}).get("metadata", {}).get("fix", ""),
                        cwe_id=result_item.get("extra", {}).get("metadata", {}).get("cwe_id", [None])[0],
                        auto_fixable=False,
                    )
                )
            return findings, []
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return [], [f"Semgrep failed for {file_path}: {e}"]
        except json.JSONDecodeError:
            return [], []
