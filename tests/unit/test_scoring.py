"""Tests for quality scoring algorithm."""

from src.agents.state import Finding
from src.scoring.quality_score import calculate_quality_score, categorize_findings


class TestQualityScore:
    def test_perfect_score(self):
        score = calculate_quality_score([], 10)
        assert score == 100.0

    def test_critical_penalty(self):
        findings = [
            Finding(severity="critical", category="security", title="X", file="a.py"),
        ]
        score = calculate_quality_score(findings, 10)
        assert score < 100.0
        assert score > 0

    def test_many_critical_issues(self):
        findings = [Finding(severity="critical", category="security", title=f"X{i}", file="a.py") for i in range(10)]
        score = calculate_quality_score(findings, 10)
        assert score < 50  # 10 criticals should bring it below 50

    def test_low_issues_small_penalty(self):
        findings = [
            Finding(severity="low", category="style", title="X", file="a.py"),
        ]
        score = calculate_quality_score(findings, 10)
        assert score > 94  # Single low issue shouldn't hurt much

    def test_score_never_negative(self):
        findings = [Finding(severity="critical", category="security", title=f"X{i}", file="a.py") for i in range(100)]
        score = calculate_quality_score(findings, 1)
        assert score >= 0


class TestCategorizeFindings:
    def test_categorizes_by_severity(self):
        findings = [
            Finding(severity="critical", category="security", title="A", file="a.py"),
            Finding(severity="high", category="security", title="B", file="a.py"),
            Finding(severity="high", category="performance", title="C", file="a.py"),
        ]
        cat = categorize_findings(findings)
        assert cat["total"] == 3
        assert cat["by_severity"]["critical"] == 1
        assert cat["by_severity"]["high"] == 2
        assert cat["by_category"]["security"] == 2
        assert cat["by_category"]["performance"] == 1
