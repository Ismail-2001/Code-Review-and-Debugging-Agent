"""Quality scoring algorithm."""

from __future__ import annotations

import math

from src.agents.state import Finding


def calculate_quality_score(findings: list[Finding], total_files: int) -> float:
    """Calculate a 0-100 code quality score based on findings.

    Score starts at 100 and is reduced by weighted penalties:
    - Critical issues: -15 points each
    - High issues: -8 points each
    - Medium issues: -3 points each
    - Low issues: -1 point each

    Security and logic issues are weighted 2x because they indicate
    deeper problems than style or performance issues.
    """
    WEIGHTS = {
        "critical": 15.0,
        "high": 8.0,
        "medium": 3.0,
        "low": 1.0,
        "info": 0.0,
    }

    CATEGORY_MULTIPLIERS = {
        "security": 2.0,
        "logic_verification": 1.8,
        "performance": 1.2,
        "testing_assessment": 1.0,
        "pattern_analysis": 0.8,
    }

    score = 100.0

    if not findings:
        return 100.0

    for finding in findings:
        severity = finding.get("severity", "info")
        category = finding.get("category", "general")

        weight = WEIGHTS.get(severity, 1.0)
        multiplier = CATEGORY_MULTIPLIERS.get(category, 1.0)

        penalty = weight * multiplier
        score -= penalty

    # Normalize by file count (larger repos get slight buffer)
    file_factor = 1 + math.log10(max(total_files, 1)) * 0.05
    score = max(0, min(100, score / file_factor))

    return round(score, 1)


def categorize_findings(findings: list[Finding]) -> dict:
    """Categorize findings by severity and category."""
    severity_counts = {
        "critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0,
    }
    category_counts: dict[str, int] = {}

    for f in findings:
        sev = f.get("severity", "info")
        if sev in severity_counts:
            severity_counts[sev] += 1

        cat = f.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        "total": len(findings),
        "by_severity": severity_counts,
        "by_category": category_counts,
    }
