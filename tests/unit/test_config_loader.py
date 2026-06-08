"""Tests for configuration loader."""

import os
import tempfile
import yaml

import pytest
from src.utils.config_loader import load_config, _deep_merge


class TestConfigLoader:
    def test_returns_defaults_when_no_config(self):
        config = load_config("/tmp/nonexistent_path_xyz")
        assert config["severity_threshold"] == "medium"
        assert "static_analysis" in config["enabled_checks"]

    def test_merges_user_config_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, ".codeguardian.yml")
            with open(config_path, "w") as f:
                yaml.dump({"severity_threshold": "critical"}, f)

            config = load_config(tmpdir)
            assert config["severity_threshold"] == "critical"
            assert config["auto_fix"]["enabled"] is True  # From defaults

    def test_deep_merge(self):
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 99}}
        result = _deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"]["c"] == 99
        assert result["b"]["d"] == 3

    def test_enabled_checks_default(self):
        config = load_config("/tmp/nonexistent")
        assert "security_audit" in config["enabled_checks"]
        assert "logic_verification" in config["enabled_checks"]
