"""Professional markdown report generator — FAANG-grade output."""

from __future__ import annotations

import datetime
from typing import Any


SEVERITY_ICONS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    "info": "ℹ️",
}


class MarkdownReporter:
    """Generates clean, professional markdown reports from findings."""

    def generate(
        self,
        findings: list[dict],
        quality_score: float,
        summary: dict,
        repo_url: str = "local",
    ) -> str:
        """Generate a complete markdown report."""
        lines: list[str] = []
        lines.append("# CodeGuardian Review Report")
        lines.append("")
        lines.append(f"**Repository**: {repo_url}")
        lines.append(f"**Date**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Quality Score**: {self._score_bar(quality_score)} **{quality_score}/100**")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Issues | **{summary.get('total', 0)}** |")

        for sev in ("critical", "high", "medium", "low", "info"):
            count = summary.get("by_severity", {}).get(sev, 0)
            icon = SEVERITY_ICONS.get(sev, "")
            lines.append(f"| {icon} {sev.capitalize()} | {count} |")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Quick Wins
        quick_wins = [f for f in findings if f.get("auto_fixable")][:10]
        if quick_wins:
            lines.append("## ⚡ Quick Wins (Auto-Fixable)")
            lines.append("")
            for f in quick_wins:
                icon = SEVERITY_ICONS.get(f.get("severity", "info"), "")
                lines.append(f"- {icon} **{f.get('title')}** — {f.get('file')}:{f.get('line', '?')}")
            lines.append("")
            lines.append("---")
            lines.append("")

        # Detailed Findings
        lines.append("## Detailed Findings")
        lines.append("")

        if not findings:
            lines.append("No issues found. ✨")
        else:
            for i, f in enumerate(findings, 1):
                severity = f.get("severity", "info")
                icon = SEVERITY_ICONS.get(severity, "")
                title = f.get("title", "Untitled")
                file = f.get("file", "Unknown")
                line = f.get("line", "?")
                desc = f.get("description", "")
                rec = f.get("recommendation", "")
                cwe = f.get("cwe_id", "")
                cvss = f.get("cvss_score", "")

                lines.append(f"### {icon} {i}. {title}")
                lines.append("")
                lines.append(f"| Field | Value |")
                lines.append(f"|-------|-------|")
                lines.append(f"| **Severity** | `{severity.upper()}` |")
                lines.append(f"| **File** | `{file}` |")
                lines.append(f"| **Line** | `{line}` |")
                if cwe:
                    lines.append(f"| **CWE** | {cwe} |")
                if cvss:
                    lines.append(f"| **CVSS** | {cvss} |")
                if f.get("auto_fixable"):
                    lines.append(f"| **Auto-Fix** | ✅ Available |")
                lines.append("")

                lines.append(f"**Description**: {desc}")
                lines.append("")
                lines.append(f"**Recommendation**: {rec}")
                lines.append("")
                lines.append("---")
                lines.append("")

        # Quality Score Breakdown
        lines.append("## Quality Score Breakdown")
        lines.append("")
        by_cat = summary.get("by_category", {})
        if by_cat:
            lines.append("| Category | Issues |")
            lines.append("|----------|--------|")
            for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
                lines.append(f"| {cat} | {count} |")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*Report generated automatically by CodeGuardian*")

        return "\n".join(lines)

    def _score_bar(self, score: float) -> str:
        """Generate a visual score bar."""
        filled = max(0, min(20, int(score / 5)))
        empty = 20 - filled
        color = "🟢" if score >= 80 else "🟡" if score >= 50 else "🔴"
        return color + "█" * filled + "░" * empty
