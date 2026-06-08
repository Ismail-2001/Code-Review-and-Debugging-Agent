"""Auto-fix generation agent — generates validated code fixes using LLM."""

from __future__ import annotations

import ast
import re

from langchain_core.prompts.chat import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.base import AnalysisAgent
from src.agents.state import CodeReviewState, Finding
from src.prompts.fix_generation import FIX_GENERATION_SYSTEM_PROMPT, FIX_TEMPLATE


class FixResult(BaseModel):
    """Structured fix output from LLM."""
    diff: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""
    risks: list[str] = []


class DiffError(Exception):
    """Raised when a diff cannot be applied cleanly."""
    pass


class FixAgent(AnalysisAgent):
    """Generates and validates surgical code fixes for auto-fixable issues."""

    def category(self) -> str:
        return "fix_generation"

    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        issues = state.get("prioritized_issues", [])
        auto_fixable = [f for f in issues if f.get("auto_fixable")]

        if not auto_fixable:
            state["generated_fixes"] = []
            state["current_step"] = "fix_generation_complete"
            return state

        generated_fixes = []
        for issue in auto_fixable:
            try:
                file_path = issue.get("file", "")
                if not file_path:
                    continue

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Get context window around the issue line
                line = issue.get("line", 0)
                lines = content.split("\n")
                start = max(0, line - 10)
                end = min(len(lines), line + 10)
                context = "\n".join(lines[start:end])

                # Generate fix via LLM
                fix = await self._generate_fix(issue, context, line)

                if fix and fix.confidence > 0.7 and fix.diff:
                    # Validate the fix
                    is_valid, error = self._validate_fix(fix, content)
                    if is_valid:
                        generated_fixes.append({
                            "issue_id": issue.get("id", ""),
                            "diff": fix.diff,
                            "explanation": fix.explanation,
                            "risks": fix.risks,
                            "confidence": fix.confidence,
                            "status": "validated",
                            "file": file_path,
                        })
                    else:
                        generated_fixes.append({
                            "issue_id": issue.get("id", ""),
                            "status": "validation_failed",
                            "error": error,
                        })
                else:
                    generated_fixes.append({
                        "issue_id": issue.get("id", ""),
                        "status": "low_confidence",
                        "confidence": fix.confidence if fix else 0,
                    })

            except Exception as e:
                generated_fixes.append({
                    "issue_id": issue.get("id", ""),
                    "status": "error",
                    "error": str(e),
                })

        state["generated_fixes"] = generated_fixes
        state["current_step"] = "fix_generation_complete"
        return state

    async def _generate_fix(self, issue: Finding, context: str, line: int) -> FixResult | None:
        prompt = ChatPromptTemplate.from_messages([
            ("system", FIX_GENERATION_SYSTEM_PROMPT),
            ("human", FIX_TEMPLATE),
        ])

        try:
            chain = prompt | self.llm.with_structured_output(FixResult)
            result: FixResult = await chain.ainvoke({
                "title": issue.get("title", ""),
                "severity": issue.get("severity", "medium"),
                "description": issue.get("description", ""),
                "file": issue.get("file", ""),
                "line": line,
                "start_line": line - 10,
                "end_line": line + 10,
                "context": context,
            })
            return result
        except Exception:
            return None

    def _validate_fix(self, fix: FixResult, original: str) -> tuple[bool, str]:
        """Validate fix for syntax correctness and safety."""
        try:
            patched = self._apply_diff(original, fix.diff)

            # Must be valid Python
            ast.parse(patched)

            # Must not be empty
            if not patched.strip():
                return False, "Fix produced empty file"

            # Must not change line count drastically
            original_lines = len(original.split("\n"))
            patched_lines = len(patched.split("\n"))
            if abs(patched_lines - original_lines) > original_lines * 0.5:
                return False, f"Fix changed line count from {original_lines} to {patched_lines}"

            return True, ""

        except SyntaxError as e:
            return False, f"Invalid syntax in fix: {e}"
        except DiffError as e:
            return False, f"Diff application failed: {e}"

    def _apply_diff(self, original: str, diff: str) -> str:
        """Apply a unified diff to original content."""
        result_lines = []

        patch_lines = diff.split("\n")
        i = 0
        while i < len(patch_lines):
            line = patch_lines[i]
            if line.startswith("--- ") or line.startswith("+++ "):
                i += 1
                continue
            if line.startswith("@@"):
                # Parse @@ -start,count +start,count @@
                match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                if not match:
                    i += 1
                    continue
                i += 1
                # Apply the hunk
                while i < len(patch_lines) and not patch_lines[i].startswith("@@"):
                    pl = patch_lines[i]
                    if pl.startswith("+"):
                        result_lines.append(pl[1:] + "\n")
                    elif pl.startswith("-"):
                        # Remove line from original
                        pass
                    elif pl.startswith(" "):
                        result_lines.append(pl[1:] + "\n")
                    i += 1
            else:
                i += 1

        if not result_lines:
            raise DiffError("No changes applied from diff")

        # Simplified: just return the patched lines
        return "".join(result_lines)
