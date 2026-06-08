"""Performance analysis agent — complexity analysis + LLM bottleneck detection."""

from __future__ import annotations

import json
import subprocess
import uuid

from src.agents.base import AnalysisAgent
from src.agents.state import CodeReviewState, Finding
from src.prompts.performance import PERFORMANCE_SYSTEM_PROMPT
from src.di.container import AppContext


PERFORMANCE_TEMPLATE = """File: {file_path}

```python
{content}
```

Cyclomatic complexity data:
```json
{complexity_data}
```
"""


class PerformanceAgent(AnalysisAgent):
    """Analyzes code for performance bottlenecks and complexity issues."""

    def category(self) -> str:
        return "performance_analysis"

    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        files = state.get("target_files", [])
        findings: list[Finding] = []

        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            # 1. Cyclomatic complexity via radon
            complexity_data = self._calculate_complexity(file_path)

            # Flag high-complexity functions
            for item in complexity_data.get("complexity_data", []):
                if isinstance(item, dict) and item.get("complexity", 0) > 10:
                    findings.append(Finding(
                        id=str(uuid.uuid4()),
                        file=file_path,
                        line=item.get("lineno", 0),
                        severity="high",
                        category="performance",
                        title="High Cyclomatic Complexity",
                        description=f"Function '{item.get('name')}' has complexity "
                                    f"{item.get('complexity')} (>10). Hard to test and maintain.",
                        recommendation=f"Reduce complexity of '{item.get('name')}' by "
                                       f"extracting conditions into helper functions.",
                        auto_fixable=False,
                    ))

            # 2. LLM-based performance analysis
            llm_findings = await self.analyze_with_llm(
                system_prompt=PERFORMANCE_SYSTEM_PROMPT,
                human_template=PERFORMANCE_TEMPLATE,
                template_vars={
                    "file_path": file_path,
                    "content": content,
                    "complexity_data": json.dumps(complexity_data, indent=2),
                },
                file_path=file_path,
            )
            findings.extend(llm_findings)

        state["performance_findings"] = findings
        state["current_step"] = "performance_analysis_complete"
        return state

    def _calculate_complexity(self, file_path: str) -> dict:
        try:
            result = subprocess.run(
                ["radon", "cc", file_path, "-j"],
                capture_output=True, text=True, timeout=10,
            )
            if result.stdout:
                data = json.loads(result.stdout)
                return {
                    "file": file_path,
                    "complexity_data": data.get(file_path, []),
                }
            return {"file": file_path, "complexity_data": []}
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            return {"file": file_path, "complexity_data": []}
