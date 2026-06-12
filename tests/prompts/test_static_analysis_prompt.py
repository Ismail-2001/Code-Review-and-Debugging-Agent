"""Validate static analysis prompt — focus areas and output schema."""

from src.prompts.static_analysis import STATIC_ANALYSIS_SYSTEM_PROMPT


class TestStaticAnalysisPrompt:
    def test_covers_logic_errors(self):
        assert "logic" in STATIC_ANALYSIS_SYSTEM_PROMPT.lower()

    def test_covers_type_safety(self):
        assert "type" in STATIC_ANALYSIS_SYSTEM_PROMPT.lower()

    def test_covers_dead_code(self):
        assert "dead code" in STATIC_ANALYSIS_SYSTEM_PROMPT.lower()

    def test_covers_error_handling(self):
        assert "error handling" in STATIC_ANALYSIS_SYSTEM_PROMPT.lower()

    def test_no_linter_duplication(self):
        assert "Do NOT report pylint" in STATIC_ANALYSIS_SYSTEM_PROMPT

    def test_no_style_suggestions(self):
        assert "Do NOT suggest style" in STATIC_ANALYSIS_SYSTEM_PROMPT

    def test_specifies_output_format(self):
        assert "file" in STATIC_ANALYSIS_SYSTEM_PROMPT
        assert "severity" in STATIC_ANALYSIS_SYSTEM_PROMPT
        assert "description" in STATIC_ANALYSIS_SYSTEM_PROMPT

    def test_has_category_options(self):
        assert any(
            cat in STATIC_ANALYSIS_SYSTEM_PROMPT
            for cat in [
                "type_safety",
                "api_misuse",
                "dead_code",
            ]
        )
