"""Validate security prompt quality — ensure CWE coverage and output format."""

from src.prompts.security import SECURITY_SYSTEM_PROMPT


class TestSecurityPrompt:
    """Ensures the security prompt has proper CWE coverage and output formatting."""

    def test_covers_sql_injection(self):
        assert "CWE-89" in SECURITY_SYSTEM_PROMPT

    def test_covers_xss(self):
        assert "CWE-79" in SECURITY_SYSTEM_PROMPT

    def test_covers_command_injection(self):
        assert any(cwe in SECURITY_SYSTEM_PROMPT for cwe in ["CWE-77", "CWE-78"])

    def test_covers_path_traversal(self):
        assert "CWE-22" in SECURITY_SYSTEM_PROMPT

    def test_covers_insecure_deserialization(self):
        assert "CWE-502" in SECURITY_SYSTEM_PROMPT

    def test_covers_ssrf(self):
        assert "CWE-918" in SECURITY_SYSTEM_PROMPT

    def test_covers_hardcoded_credentials(self):
        assert "CWE-798" in SECURITY_SYSTEM_PROMPT

    def test_specifies_output_format(self):
        assert "cwe_id" in SECURITY_SYSTEM_PROMPT
        assert "cvss_score" in SECURITY_SYSTEM_PROMPT

    def test_specifies_severity_levels(self):
        assert "critical" in SECURITY_SYSTEM_PROMPT
        assert "high" in SECURITY_SYSTEM_PROMPT
        assert "medium" in SECURITY_SYSTEM_PROMPT
        assert "low" in SECURITY_SYSTEM_PROMPT

    def test_no_false_positive_guidance(self):
        assert any(phrase in SECURITY_SYSTEM_PROMPT for phrase in [
            "false positive", "unsure", "Do NOT report", "If you are not confident",
        ])
