"""Configuration loader — handles YAML config with sensible defaults."""

from __future__ import annotations

import os
from pathlib import Path

import yaml


DEFAULT_CONFIG: dict = {
    "enabled_checks": [
        "static_analysis",
        "pattern_analysis",
        "security_audit",
        "performance_analysis",
        "testing_assessment",
        "logic_verification",
        "policy_verification",
    ],
    "severity_threshold": "medium",
    "exclude_patterns": [
        "**/node_modules/**",
        "**/vendor/**",
        "**/dist/**",
        "**/build/**",
        "**/*.test.js",
        "**/*.spec.py",
        "**/__pycache__/**",
        ".git/**",
    ],
    "include_patterns": ["**/*.py", "**/*.js", "**/*.ts", "**/*.tsx", "**/*.java"],
    "auto_fix": {"enabled": True, "safe_only": True},
    "max_analysis_time": 600,
    "max_files_per_review": 5000,
    "llm_provider": "google",
    "llm_model": "gemini-2.0-flash-exp",
    "llm_temperature": 0.1,
    "performance": {
        "max_function_lines": 50,
        "max_class_lines": 300,
        "check_n_plus_one": True,
        "complexity_threshold": 10,
    },
    "security": {
        "scan_dependencies": True,
        "check_secrets": True,
        "fail_on_critical": True,
    },
    "reporting": {
        "formats": ["markdown", "json"],
        "include_code_snippets": True,
        "max_findings_in_report": 200,
    },
}


def load_config(config_path_or_repo: str | None = None) -> dict:
    """Load configuration from a file or repository root.

    Args:
        config_path_or_repo: Path to config file or repo root directory.
                             If None, looks in current directory.

    Returns:
        Complete config dict (defaults merged with user config).
    """
    if config_path_or_repo is None:
        config_path_or_repo = os.getcwd()

    path = Path(config_path_or_repo)

    if path.is_dir():
        config_file = path / ".codeguardian.yml"
    else:
        config_file = path

    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                user_config = yaml.safe_load(f)
                if user_config and isinstance(user_config, dict):
                    return _deep_merge(DEFAULT_CONFIG.copy(), user_config)
        except (yaml.YAMLError, OSError):
            pass

    return DEFAULT_CONFIG.copy()


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries — override values take precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
