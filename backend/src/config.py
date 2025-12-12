import yaml
import os
from pathlib import Path

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")

def load_config():
    path = Path(CONFIG_PATH)
    if not path.exists():
        # Fallback for local dev if not running in docker and path not set
        local_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
        if local_path.exists():
            path = local_path
        else:
            raise FileNotFoundError(f"Config file not found at {CONFIG_PATH} or {local_path}")
    
    with open(path, "r") as f:
        return yaml.safe_load(f)
