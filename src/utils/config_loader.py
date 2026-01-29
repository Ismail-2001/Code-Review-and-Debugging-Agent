import yaml
import os
from pathlib import Path
from typing import Dict

def load_config(config_path_or_repo: str) -> Dict:
    """Load configuration from a file or repository root."""
    path = Path(config_path_or_repo)
    if not path.suffix == ".yml":
        path = path / ".codeguardian.yml"
    
    default_config = {
        "enabled_checks": ["static_analysis", "security_audit", "performance_analysis"],
        "severity_threshold": "medium",
        "auto_fix": {"enabled": True}
    }
    
    if path.exists():
        with open(path, 'r') as f:
            user_config = yaml.safe_load(f)
            if user_config:
                return {**default_config, **user_config}
    
    return default_config
