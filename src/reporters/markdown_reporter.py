"""Professional markdown report generator — FAANG-grade output."""

from __future__ import annotations

import datetime

SEVERITY_LABELS = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "info": "INFO",
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
        self._add_header(lines, quality_score, repo_url)
        self._add_executive_summary(lines, summary)
        self._add_quick_wins(lines, findings)
        self._add_detailed_findings(lines, findings)
        self._add_quality_breakdown(lines, summary)
        self._add_footer(lines)
        return "\n".join(lines)

    @staticmethod
    def _add_separator(lines: list[str]):
        lines.extend(["", "---", ""])

    def _add_header(self, lines: list[str], score: float, repo_url: str):
        lines.append("# CodeGuardian Review Report")
        lines.append("")
        lines.append(f"**Repository**: {repo_url}")
        lines.append(f"**Date**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Quality Score**: **{score}/100**")
        self._add_separator(lines)

    def _add_executive_summary(self, lines: list[str], summary: dict):
        lines.append("## Executive Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Issues | **{summary.get('total', 0)}** |")
        for sev in ("critical", "high", "medium", "low", "info"):
            count = summary.get("by_severity", {}).get(sev, 0)
            lines.append(f"| {sev.capitalize()} | {count} |")
        self._add_separator(lines)

    def _add_quick_wins(self, lines: list[str], findings: list[dict]):
        quick_wins = [f for f in findings if f.get("auto_fixable")][:10]
        if not quick_wins:
            return
        lines.append("## Quick Wins (Auto-Fixable)")
        lines.append("")
        for f in quick_wins:
            sev = SEVERITY_LABELS.get(f.get("severity", "info"), "INFO")
            lines.append(f"- **[{sev}]** {f.get('title')} — {f.get('file')}:{f.get('line', '?')}")
        self._add_separator(lines)

    def _add_detailed_findings(self, lines: list[str], findings: list[dict]):
        lines.append("## Detailed Findings")
        lines.append("")
        if not findings:
            lines.append("No issues found.")
            return
        for i, f in enumerate(findings, 1):
            severity = SEVERITY_LABELS.get(f.get("severity", "info"), "INFO")
            title = f.get("title", "Untitled")
            file = f.get("file", "Unknown")
            line = f.get("line", "?")
            desc = f.get("description", "")
            rec = f.get("recommendation", "")
            cwe = f.get("cwe_id", "")
            cvss = f.get("cvss_score", "")

            lines.append(f"### {i}. [{severity}] {title}")
            lines.append("")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            lines.append(f"| Severity | `{severity}` |")
            lines.append(f"| File | `{file}` |")
            lines.append(f"| Line | `{line}` |")
            if cwe:
                lines.append(f"| CWE | {cwe} |")
            if cvss:
                lines.append(f"| CVSS | {cvss} |")
            if f.get("auto_fixable"):
                lines.append("| Auto-Fix | Available |")
            lines.append("")
            lines.append(f"**Description**: {desc}")
            lines.append("")
            lines.append(f"**Recommendation**: {rec}")
            self._add_separator(lines)

    def _add_quality_breakdown(self, lines: list[str], summary: dict):
        lines.append("## Quality Score Breakdown")
        lines.append("")
        by_cat = summary.get("by_category", {})
        if by_cat:
            lines.append("| Category | Issues |")
            lines.append("|----------|--------|")
            for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
                lines.append(f"| {cat} | {count} |")
        self._add_separator(lines)

    def _add_footer(self, lines: list[str]):
        lines.append("*Report generated automatically by CodeGuardian*")
