"""Explicit, non-secret provider configuration; keys are never read from files."""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config/model.json"


def model_settings(path=None):
    path = DEFAULT_CONFIG if path is None else Path(path)
    data = json.loads(path.read_text("utf-8")) if path.is_file() else {}
    if not isinstance(data, dict) or set(data)-{"base_url", "model"}:
        raise ValueError("Provider file must contain only base_url and model, never credentials")
    if any(not isinstance(value, str) for value in data.values()):
        raise ValueError("Provider configuration values must be strings")
    base = (os.getenv("LLM_BASE_URL") or data.get("base_url") or "").strip().rstrip("/")
    name = (os.getenv("LLM_MODEL") or data.get("model") or "").strip()
    if base:
        parsed = urlsplit(base)
        if ("\n" in base or "\r" in base or parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port not in (None,443)):
            raise ValueError("Provider base must be an HTTPS API URL without credentials or query parameters")
    if name and (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}", name) or name.lower().startswith("sk-")):
        raise ValueError("Model must be a model identifier, never a credential")
    return base, name
