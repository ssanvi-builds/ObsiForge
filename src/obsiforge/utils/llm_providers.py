"""LLM provider configuration for claude-mem."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class ProviderInfo(TypedDict):
    display_name: str
    needs_api_key: bool
    default_model: str
    key_prefix: str | None
    settings_key: str | None
    model_settings_key: str | None
    extra_settings: dict[str, Any]
    warning: str | None


def get_claude_mem_settings_path() -> Path:
    """Return path to claude-mem settings.json."""
    return Path.home() / ".claude-mem" / "settings.json"


def load_claude_mem_settings() -> dict[str, Any]:
    """Load claude-mem settings.json, returning empty dict if missing."""
    path = get_claude_mem_settings_path()
    if not path.exists():
        return {}
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def save_claude_mem_settings(settings: dict[str, Any]) -> None:
    """Write claude-mem settings.json, creating parent dirs if needed."""
    path = get_claude_mem_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


PROVIDERS: dict[str, ProviderInfo] = {
    "gemini": {
        "display_name": "Gemini Flash (free, recommended)",
        "needs_api_key": True,
        "default_model": "gemini-2.5-flash-lite",
        "key_prefix": "AI",
        "settings_key": "CLAUDE_MEM_GEMINI_API_KEY",
        "model_settings_key": "CLAUDE_MEM_GEMINI_MODEL",
        "extra_settings": {
            "CLAUDE_MEM_GEMINI_RATE_LIMITING_ENABLED": "true",
            "CLAUDE_MEM_GEMINI_MAX_CONTEXT_MESSAGES": "20",
            "CLAUDE_MEM_GEMINI_MAX_TOKENS": "100000",
        },
        "warning": None,
    },
    "openrouter": {
        "display_name": "OpenRouter (free tier — often unreliable)",
        "needs_api_key": True,
        "default_model": "xiaomi/mimo-v2-flash:free",
        "key_prefix": "sk-or",
        "settings_key": "CLAUDE_MEM_OPENROUTER_API_KEY",
        "model_settings_key": "CLAUDE_MEM_OPENROUTER_MODEL",
        "extra_settings": {
            "CLAUDE_MEM_OPENROUTER_MAX_CONTEXT_MESSAGES": "20",
            "CLAUDE_MEM_OPENROUTER_MAX_TOKENS": "100000",
            "CLAUDE_MEM_OPENROUTER_SITE_URL": "",
            "CLAUDE_MEM_OPENROUTER_APP_NAME": "claude-mem",
        },
        "warning": (
            "OpenRouter free-tier models frequently timeout or "
            "produce errors. Gemini Flash is recommended."
        ),
    },
    "anthropic": {
        "display_name": "Anthropic (subscription auth, no key needed)",
        "needs_api_key": False,
        "default_model": "claude-haiku-4-5-20251001",
        "key_prefix": None,
        "settings_key": None,
        "model_settings_key": "CLAUDE_MEM_MODEL",
        "extra_settings": {
            "CLAUDE_MEM_CLAUDE_AUTH_METHOD": "subscription",
        },
        "warning": None,
    },
}


def validate_api_key(provider_id: str, key: str) -> bool:
    """Basic format validation for an API key.

    Returns True if the key looks plausible (non-empty, expected prefix).
    Does NOT verify the key works by calling the API.
    """
    provider = PROVIDERS.get(provider_id)
    if not provider:
        return False
    if not key or not key.strip():
        return False
    prefix = provider.get("key_prefix")
    return not (isinstance(prefix, str) and not key.startswith(prefix))


def is_provider_configured(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Check if an LLM provider is properly configured in claude-mem settings.

    Returns dict with keys: configured (bool), provider (str), details (str).
    """
    if settings is None:
        settings = load_claude_mem_settings()

    provider_id = settings.get("CLAUDE_MEM_PROVIDER", "")

    if provider_id == "gemini":
        key = settings.get("CLAUDE_MEM_GEMINI_API_KEY", "")
        if key:
            masked = f"...{key[-4:]}" if len(key) > 4 else "***"
            return {
                "configured": True,
                "provider": "gemini",
                "details": f"Gemini (key: {masked})",
            }
        return {
            "configured": False,
            "provider": "gemini",
            "details": "Gemini selected but API key missing",
        }

    if provider_id == "openrouter":
        key = settings.get("CLAUDE_MEM_OPENROUTER_API_KEY", "")
        if key:
            masked = f"...{key[-4:]}" if len(key) > 4 else "***"
            return {
                "configured": True,
                "provider": "openrouter",
                "details": f"OpenRouter (key: {masked})",
            }
        return {
            "configured": False,
            "provider": "openrouter",
            "details": "OpenRouter selected but API key missing",
        }

    if provider_id == "anthropic":
        return {
            "configured": True,
            "provider": "anthropic",
            "details": "Anthropic subscription auth",
        }

    if provider_id == "":
        # No explicit provider selected — not a deliberate configuration
        return {
            "configured": False,
            "provider": "none",
            "details": "No LLM provider configured",
        }

    return {
        "configured": False,
        "provider": provider_id,
        "details": f"Unknown provider: {provider_id}",
    }


def configure_provider(
    provider_id: str,
    api_key: str = "",
) -> dict[str, Any]:
    """Configure an LLM provider in claude-mem settings.

    Writes only the keys relevant to the chosen provider.
    Preserves all existing settings.
    """
    provider = PROVIDERS.get(provider_id)
    if not provider:
        return {"success": False, "error": f"Unknown provider: {provider_id}"}

    if provider["needs_api_key"] and not api_key:
        return {"success": False, "error": f"API key required for {provider_id}"}

    if provider["needs_api_key"] and not validate_api_key(provider_id, api_key):
        return {"success": False, "error": f"API key format invalid for {provider_id}"}

    settings = load_claude_mem_settings()
    settings["CLAUDE_MEM_PROVIDER"] = provider_id

    # Set API key if provider needs one
    settings_key: str | None = provider["settings_key"]
    if settings_key and api_key:
        settings[settings_key] = api_key

    # Set model
    model_key: str | None = provider["model_settings_key"]
    if model_key:
        settings[model_key] = provider["default_model"]

    # Set extra settings (rate limiting, etc.)
    extra: dict[str, Any] = provider["extra_settings"]
    for key, value in extra.items():
        settings[key] = value

    save_claude_mem_settings(settings)

    return {"success": True, "provider": provider_id, "model": provider["default_model"]}