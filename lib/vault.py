"""
Secrets Vault — centralised loader for all sensitive configuration values.

Priority order (highest to lowest):
  1. ``config/secrets.yaml``  — local secrets file (never commit to VCS)
  2. Environment variables     — useful for containers / CI pipelines

Environment-variable names
--------------------------
Each secret maps to a well-known env var name so the vault can be used
without the secrets file:

  WATSONX_API_KEY            → ai_agent.chaimera3sp.providers.watsonx.api_key
  WATSONX_PROJECT_ID         → ai_agent.chaimera3sp.providers.watsonx.project_id
  KIMI_API_KEY               → ai_agent.chaimera3sp.providers.kimi.api_key
  KAI9000_API_KEY            → ai_agent.chaimera3sp.providers.kai9000.api_key
  MANUS_API_KEY              → ai_agent.chaimera3sp.providers.manus.api_key
  CLOUD_API_KEY              → comms_agent.api_key  (HTTP cloud connector)
  AZURE_CONNECTION_STRING    → comms_agent.azure_connection_string

Usage
-----
::

    from lib.vault import load_secrets
    config = load_config("config/default.yaml")
    load_secrets(config)   # mutates config in-place; secrets take precedence
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default path for the secrets file (relative to the project root).
_DEFAULT_SECRETS_FILE = Path(__file__).parent.parent / "config" / "secrets.yaml"

# Mapping of environment-variable names to dotted config key paths.
_ENV_MAPPINGS: Dict[str, str] = {
    "WATSONX_API_KEY":         "ai_agent.chaimera3sp.providers.watsonx.api_key",
    "WATSONX_PROJECT_ID":      "ai_agent.chaimera3sp.providers.watsonx.project_id",
    "KIMI_API_KEY":            "ai_agent.chaimera3sp.providers.kimi.api_key",
    "KAI9000_API_KEY":         "ai_agent.chaimera3sp.providers.kai9000.api_key",
    "MANUS_API_KEY":           "ai_agent.chaimera3sp.providers.manus.api_key",
    "CLOUD_API_KEY":           "comms_agent.api_key",
    "AZURE_CONNECTION_STRING": "comms_agent.azure_connection_string",
}


def _deep_set(mapping: Dict[str, Any], dotted_key: str, value: Any) -> None:
    """Set a value in a nested dict using a dotted key path, creating dicts as needed."""
    keys = dotted_key.split(".")
    node = mapping
    for key in keys[:-1]:
        node = node.setdefault(key, {})
    node[keys[-1]] = value


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """Recursively merge *override* into *base* in-place."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _load_secrets_file(path: Path) -> Dict[str, Any]:
    """Return the parsed YAML dict from *path*, or an empty dict if unavailable."""
    if not path.exists():
        return {}
    try:
        import yaml  # PyYAML — already a project dependency
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            logger.warning("vault: %s did not contain a YAML mapping — ignored", path)
            return {}
        logger.debug("vault: loaded secrets from %s", path)
        return data
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("vault: could not load secrets file %s: %s", path, exc)
        return {}


def _secrets_from_env() -> Dict[str, Any]:
    """Build a config dict from environment variables using :data:`_ENV_MAPPINGS`."""
    result: Dict[str, Any] = {}
    for env_var, dotted_key in _ENV_MAPPINGS.items():
        value = os.environ.get(env_var)
        if value:
            _deep_set(result, dotted_key, value)
            logger.debug("vault: applied %s → %s", env_var, dotted_key)
    return result


def load_secrets(
    config: Dict[str, Any],
    secrets_file: Optional[Path] = None,
) -> None:
    """
    Inject secrets into *config* in-place.

    Secrets are loaded first from *secrets_file* (default:
    ``config/secrets.yaml``), then from environment variables.
    Environment variables always take precedence over the file.

    Args:
        config:       The main configuration dict to augment (mutated in-place).
        secrets_file: Override the default secrets file path.
    """
    path = Path(secrets_file) if secrets_file else _DEFAULT_SECRETS_FILE

    file_secrets = _load_secrets_file(path)
    env_secrets = _secrets_from_env()

    # env vars override file values
    _deep_merge(file_secrets, env_secrets)

    if file_secrets:
        _deep_merge(config, file_secrets)
        logger.info("vault: secrets applied to config")
    else:
        logger.debug("vault: no secrets found (file absent and no env vars set)")
