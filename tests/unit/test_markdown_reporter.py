"""Tests for markdown reporter."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest

from reporters.markdown_reporter import MarkdownReporter


@pytest.fixture
def reporter():
    return MarkdownReporter()


def test_generates_report_header(reporter):
    report = reporter.generate([], 100.0, {"total": 0, "by_severity": {}, "by_category": {}}, "test/repo")
    assert "# CodeGuardian Review Report" in report
    assert "100.0/100" in report


def test_includes_findings(reporter):
    findings = [
        {
            "severity": "high",
            "category": "security",
            "title": "SQL Injection",
            "description": "Raw SQL in query",
            "recommendation": "Use parameterized queries",
            "file": "db.py",
            "line": 42,
            "auto_fixable": False,
        }
    ]
    summary = {
        "total": 1,
        "by_severity": {"critical": 0, "high": 1, "medium": 0, "low": 0, "info": 0},
        "by_category": {"security": 1},
    }
    report = reporter.generate(findings, 85.0, summary, "test/repo")

    assert "SQL Injection" in report
    assert "Raw SQL in query" in report
    assert "85.0/100" in report


def test_empty_report(reporter):
    report = reporter.generate(
        [],
        100.0,
        {"total": 0, "by_severity": {}, "by_category": {}},
        "test/repo",
    )
    assert "No issues found" in report or "Quality Score" in report


def test_quick_wins_section(reporter):
    findings = [
        {
            "severity": "medium",
            "category": "style",
            "title": "Fixable",
            "file": "a.py",
            "line": 1,
            "description": "Test",
            "recommendation": "Fix it",
            "auto_fixable": True,
        }
    ]
    summary = {
        "total": 1,
        "by_severity": {"critical": 0, "high": 0, "medium": 1, "low": 0, "info": 0},
        "by_category": {"style": 1},
    }
    report = reporter.generate(findings, 95.0, summary, "test/repo")
    assert "Quick Wins" in report or "Auto-Fixable" in report
