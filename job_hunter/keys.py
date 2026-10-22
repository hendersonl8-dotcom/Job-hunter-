"""The Claude API key, saved on this computer so nobody has to set environment variables.

The key lives in keys.json in the user's data folder (never in the project, never uploaded). An
ANTHROPIC_API_KEY already set in the environment is left alone and takes priority at start-up.
"""

from __future__ import annotations

import json
import os

import anthropic

from . import userdata

KEYS_FILE = "keys.json"
ENV_VAR = "ANTHROPIC_API_KEY"


def has_claude_key() -> bool:
    return bool(os.environ.get(ENV_VAR) or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _path():
    return userdata.user_dir() / KEYS_FILE


def _saved() -> dict:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_into_env() -> None:
    """Make the saved Claude key available to the app, unless one is already set."""
    key = _saved().get("anthropic_api_key", "")
    if key and not has_claude_key():
        os.environ[ENV_VAR] = key


def check_claude_key(key: str, client: anthropic.Anthropic | None = None) -> str:
    """"" if the key works, otherwise a plain-English reason. A network problem is reported, not treated as a bad key."""
    key = key.strip()
    if not key.startswith("sk-ant-"):
        return "That doesn't look like a Claude key. It starts with sk-ant-."
    try:
        (client or anthropic.Anthropic(api_key=key)).models.list(limit=1)
    except anthropic.AuthenticationError:
        return "Claude didn't accept that key. Copy it again from console.anthropic.com."
    except anthropic.APIConnectionError:
        return "Couldn't reach Claude to check the key. Check your internet connection and try again."
    except anthropic.APIError as exc:
        return f"Claude couldn't check the key: {exc}"
    return ""


def save_claude_key(key: str) -> None:
    key = key.strip()
    userdata.write_json(_path(), {**_saved(), "anthropic_api_key": key})
    try:
        _path().chmod(0o600)
    except OSError:
        pass
    os.environ[ENV_VAR] = key


def forget_claude_key() -> None:
    saved = _saved()
    saved.pop("anthropic_api_key", None)
    userdata.write_json(_path(), saved)
    os.environ.pop(ENV_VAR, None)
