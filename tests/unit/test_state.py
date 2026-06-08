"""Tests for state definitions and helpers."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from agents.state import Finding, sort_by_severity


class TestSortBySeverity:
    def test_sorts_critical_first(self):
        findings = [
            Finding(severity="low", title="Low", file="a.py", id="1"),
            Finding(severity="critical", title="Critical", file="a.py", id="2"),
            Finding(severity="high", title="High", file="a.py", id="3"),
        ]
        sorted_f = sort_by_severity(findings)
        assert sorted_f[0]["severity"] == "critical"
        assert sorted_f[1]["severity"] == "high"
        assert sorted_f[2]["severity"] == "low"

    def test_handles_unknown_severity(self):
        findings = [
            Finding(severity="unknown", title="X", file="a.py", id="1"),
            Finding(severity="critical", title="C", file="a.py", id="2"),
        ]
        sorted_f = sort_by_severity(findings)
        assert sorted_f[0]["severity"] == "critical"

    def test_empty_list(self):
        assert sort_by_severity([]) == []

    def test_maintains_order_within_same_severity(self):
        findings = [
            Finding(severity="medium", title="A", file="a.py", id="1"),
            Finding(severity="medium", title="B", file="a.py", id="2"),
        ]
        sorted_f = sort_by_severity(findings)
        assert sorted_f[0]["title"] == "A"
        assert sorted_f[1]["title"] == "B"
