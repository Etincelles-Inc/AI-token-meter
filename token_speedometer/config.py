import json
import os
from pathlib import Path
from urllib.parse import urlsplit

APP_ID = "com.etincelles.TokenMeter"
OWNER = "etincelles-token-meter-install-v1"

def data_dir():
    if os.environ.get("ETINCELLES_TOKEN_METER_HOME"):
        return Path(os.environ["ETINCELLES_TOKEN_METER_HOME"]).expanduser().resolve()
    if os.name == "nt":
        return Path.home() / ".etincelles-token-meter"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "etincelles-token-meter"

def validate_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise ValueError("Use an HTTP(S) server URL without embedded credentials or a fragment.")
    return value.rstrip("/")

DEFAULTS = {"backend": "auto", "upstream": "http://127.0.0.1:8000", "model": "",
            "proxy_port": 18630, "always_on_top": True, "auth_env": ""}

def load_config():
    result = dict(DEFAULTS)
    path = data_dir() / "config.json"
    if path.is_file():
        result.update(json.loads(path.read_text(encoding="utf-8")))
    return validate_config(result)

def validate_config(value):
    result = {**DEFAULTS, **value}
    if result["backend"] not in ("auto", "vllm", "llamacpp", "ollama", "native"):
        raise ValueError("Unknown engine adapter.")
    result["upstream"] = validate_url(result["upstream"])
    result["proxy_port"] = int(result["proxy_port"])
    if not 1024 <= result["proxy_port"] <= 65535:
        raise ValueError("Proxy port must be between 1024 and 65535.")
    if not isinstance(result["model"], str):
        raise ValueError("Model must be a string; empty selects the latest model.")
    return result

def save_config(value):
    value = validate_config(value)
    folder = data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / ".owner"
    if marker.exists() and marker.read_text().strip() != OWNER:
        raise RuntimeError("Settings folder belongs to another application.")
    marker.write_text(OWNER, encoding="utf-8")
    temporary = folder / "config.tmp"
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(folder / "config.json")

def auth_headers(config):
    value = os.environ.get(config.get("auth_env", ""), "")
    return {"Authorization": "Bearer " + value} if value else {}
