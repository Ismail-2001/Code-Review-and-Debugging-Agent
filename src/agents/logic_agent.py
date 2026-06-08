"""Logic verification agent — the crown jewel. Deep reasoning about function intent vs implementation."""

from __future__ import annotations

import ast
import uuid

from src.agents.base import AnalysisAgent
from src.agents.state import CodeReviewState, Finding
from src.prompts.logic_verification import (
    LOGIC_VERIFICATION_SYSTEM_PROMPT,
    LOGIC_VERIFICATION_TEMPLATE,
)
from src.di.container import AppContext

import ast as ast_module


class LogicAgent(AnalysisAgent):
    """Deep logic verification — compares function implementation against documented intent.

    This is the key differentiator from every other code review tool.
    It finds bugs that linters and SAST tools cannot: logic errors, edge cases,
    and intent-implementation mismatches.
    """

    def category(self) -> str:
        return "logic_verification"

    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        files = state.get("target_files", [])
        findings: list[Finding] = []

        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            # Parse AST to find function boundaries
            try:
                tree = ast_module.parse(content, filename=file_path)
            except SyntaxError:
                continue

            functions = [
                n for n in ast_module.walk(tree)
                if isinstance(n, (ast_module.FunctionDef, ast_module.AsyncFunctionDef))
            ]

            for func in functions:
                # Extract context
                func_code = ast_module.get_source_segment(content, func)
                if not func_code:
                    continue

                docstring = ast_module.get_docstring(func) or "No documentation provided"
                parameters = [
                    f"{a.arg}: {ast_module.unparse(a.annotation) if a.annotation else 'Any'}"
                    for a in func.args.args
                ]
                return_type = ""
                if func.returns:
                    try:
                        return_type = ast_module.unparse(func.returns)
                    except Exception:
                        return_type = "Any"

                # LLM deep reasoning
                llm_findings = await self.analyze_with_llm(
                    system_prompt=LOGIC_VERIFICATION_SYSTEM_PROMPT,
                    human_template=LOGIC_VERIFICATION_TEMPLATE,
                    template_vars={
                        "function_name": func.name,
                        "parameters": ", ".join(parameters),
                        "return_type": return_type,
                        "docstring": docstring,
                        "implementation": func_code,
                    },
                    file_path=f"{file_path}:{func.name}",
                )

                for lf in llm_findings:
                    lf["line"] = func.lineno

                findings.extend(llm_findings)

        state["logic_findings"] = findings
        state["current_step"] = "logic_verification_complete"
        return state
