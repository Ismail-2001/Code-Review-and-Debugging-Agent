import yaml
import os
from pathlib import Path
from typing import Dict

def load_config(repo_path: str) -> Dict:
    """Load .codeguardian.yml configuration."""
    config_path = Path(repo_path) / ".codeguardian.yml"
    
    default_config = {
        "enabled_checks": [
            "static_analysis",
            "security_audit",
            "performance_analysis",
            "pattern_analysis",
            "testing_assessment",
            "logic_verification"
        ],
        "severity_threshold": "medium",
        "exclude_patterns": [
            "**/node_modules/**",
            "**/vendor/**",
            "**/*.test.js",
            "**/*.spec.py"
        ],
        "auto_fix": {
            "enabled": True,
            "safe_only": True
        },
        "max_analysis_time": 600
    }
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    return {**default_config, **user_config}
        except Exception:
            pass
    
    return default_config
