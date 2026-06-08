"""Validate logic verification prompt — ensures deep reasoning framework."""

from src.prompts.logic_verification import LOGIC_VERIFICATION_SYSTEM_PROMPT


class TestLogicPrompt:
    def test_covers_intent_gap(self):
        assert "intent" in LOGIC_VERIFICATION_SYSTEM_PROMPT.lower()

    def test_covers_edge_cases(self):
        assert "Edge Case" in LOGIC_VERIFICATION_SYSTEM_PROMPT

    def test_covers_state_consistency(self):
        assert "State" in LOGIC_VERIFICATION_SYSTEM_PROMPT

    def test_covers_off_by_one(self):
        assert "Off-by-One" in LOGIC_VERIFICATION_SYSTEM_PROMPT or "off-by-one" in LOGIC_VERIFICATION_SYSTEM_PROMPT.lower()

    def test_covers_resource_mgmt(self):
        assert "Resource" in LOGIC_VERIFICATION_SYSTEM_PROMPT

    def test_confidence_threshold(self):
        assert "0.7" in LOGIC_VERIFICATION_SYSTEM_PROMPT or "confidence" in LOGIC_VERIFICATION_SYSTEM_PROMPT.lower()

    def test_severity_none_usage(self):
        assert "none" in LOGIC_VERIFICATION_SYSTEM_PROMPT
