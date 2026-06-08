"""Pattern analysis agent — detects design smells, anti-patterns, code rot."""

from __future__ import annotations

import ast

from src.agents.base import AnalysisAgent
from src.agents.state import CodeReviewState, Finding

import uuid


class PatternAgent(AnalysisAgent):
    """Detects code smells and design anti-patterns using AST heuristics + LLM."""

    def category(self) -> str:
        return "pattern_analysis"

    async def analyze(self, state: CodeReviewState) -> CodeReviewState:
        files = state.get("target_files", [])
        findings: list[Finding] = []

        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            # AST-based smell detection (deterministic, zero cost)
            try:
                tree = ast.parse(content, filename=file_path)
                findings.extend(self._detect_function_smells(file_path, tree))
                findings.extend(self._detect_class_smells(file_path, tree))
                findings.extend(self._detect_import_smells(file_path, tree))
            except SyntaxError:
                continue

        state["pattern_analysis_findings"] = findings
        state["current_step"] = "pattern_analysis_complete"
        return state

    def _detect_function_smells(self, file_path: str, tree: ast.AST) -> list[Finding]:
        findings = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            # Long function
            if hasattr(node, "end_lineno") and hasattr(node, "lineno"):
                length = node.end_lineno - node.lineno
                if length > 50:
                    findings.append(Finding(
                        id=str(uuid.uuid4()),
                        file=file_path,
                        line=node.lineno,
                        severity="medium",
                        category="pattern",
                        title="Long Function",
                        description=f"Function '{node.name}' is {length} lines long (>50). "
                                    f"Long functions are harder to understand and test.",
                        recommendation=f"Extract helper functions from '{node.name}'. "
                                       f"Aim for functions under 20 lines.",
                        auto_fixable=False,
                    ))

            # Too many parameters
            param_count = len(node.args.args)
            if param_count > 5:
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    file=file_path,
                    line=node.lineno,
                    severity="medium",
                    category="pattern",
                    title="Too Many Parameters",
                    description=f"Function '{node.name}' has {param_count} parameters (>5). "
                                f"Hard to use correctly without documentation.",
                    recommendation=f"Consider using a parameter object or kwargs pattern "
                                   f"for '{node.name}'.",
                    auto_fixable=False,
                ))

            # Too many returns
            return_count = sum(1 for n in ast.walk(node) if isinstance(n, ast.Return))
            if return_count > 5:
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    file=file_path,
                    line=node.lineno,
                    severity="low",
                    category="pattern",
                    title="Multiple Return Points",
                    description=f"Function '{node.name}' has {return_count} return statements. "
                                f"Increases cognitive complexity.",
                    recommendation=f"Consider consolidating return paths in '{node.name}'.",
                    auto_fixable=False,
                ))

        return findings

    def _detect_class_smells(self, file_path: str, tree: ast.AST) -> list[Finding]:
        findings = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            if hasattr(node, "end_lineno") and hasattr(node, "lineno"):
                length = node.end_lineno - node.lineno
                if length > 500:
                    methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    findings.append(Finding(
                        id=str(uuid.uuid4()),
                        file=file_path,
                        line=node.lineno,
                        severity="high",
                        category="pattern",
                        title="God Class",
                        description=f"Class '{node.name}' is {length} lines with "
                                    f"{len(methods)} methods (>500). Violates Single Responsibility.",
                        recommendation=f"Split '{node.name}' into smaller focused classes.",
                        auto_fixable=False,
                    ))

        return findings

    def _detect_import_smells(self, file_path: str, tree: ast.AST) -> list[Finding]:
        findings = []
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")

        # Detect wildcard imports
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.names and any(
                alias.name == "*" for alias in node.names
            ):
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    file=file_path,
                    line=node.lineno,
                    severity="low",
                    category="pattern",
                    title="Wildcard Import",
                    description=f"Wildcard import 'from {node.module} import *' pollutes namespace.",
                    recommendation="Import specific names instead of using *.",
                    auto_fixable=True,
                ))

        return findings
