import yaml
import os
from pathlib import Path

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
if not os.path.exists(CONFIG_PATH):
    # Fallback for local dev
    local_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    if local_path.exists():
        CONFIG_PATH = str(local_path)

def load_config():
    path = Path(CONFIG_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found at {CONFIG_PATH}")
    
    with open(path, "r") as f:
        return yaml.safe_load(f)


def save_config(config):
    """Save configuration back to the config file."""
    path = Path(CONFIG_PATH)
    with open(path, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
