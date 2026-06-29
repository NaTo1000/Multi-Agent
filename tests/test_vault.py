"""
Tests for lib/vault.py — secrets vault loader.
"""

import os
import textwrap
from pathlib import Path

import pytest

from lib.vault import _deep_merge, _deep_set, _secrets_from_env, load_secrets


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

class TestDeepSet:
    def test_simple_key(self):
        d = {}
        _deep_set(d, "foo", "bar")
        assert d == {"foo": "bar"}

    def test_nested_key(self):
        d = {}
        _deep_set(d, "a.b.c", "val")
        assert d == {"a": {"b": {"c": "val"}}}

    def test_overwrites_existing(self):
        d = {"a": {"b": "old"}}
        _deep_set(d, "a.b", "new")
        assert d["a"]["b"] == "new"


class TestDeepMerge:
    def test_flat(self):
        base = {"a": 1, "b": 2}
        _deep_merge(base, {"b": 99, "c": 3})
        assert base == {"a": 1, "b": 99, "c": 3}

    def test_nested(self):
        base = {"x": {"y": 1, "z": 2}}
        _deep_merge(base, {"x": {"y": 99}})
        assert base == {"x": {"y": 99, "z": 2}}

    def test_new_nested_key(self):
        base = {"a": 1}
        _deep_merge(base, {"b": {"c": 2}})
        assert base["b"]["c"] == 2


# ---------------------------------------------------------------------------
# Environment-variable secrets
# ---------------------------------------------------------------------------

class TestSecretsFromEnv:
    def test_watsonx_api_key(self, monkeypatch):
        monkeypatch.setenv("WATSONX_API_KEY", "wx-secret")
        result = _secrets_from_env()
        assert result["ai_agent"]["chaimera3sp"]["providers"]["watsonx"]["api_key"] == "wx-secret"

    def test_cloud_api_key(self, monkeypatch):
        monkeypatch.setenv("CLOUD_API_KEY", "cloud-token")
        result = _secrets_from_env()
        assert result["comms_agent"]["api_key"] == "cloud-token"

    def test_azure_connection_string(self, monkeypatch):
        monkeypatch.setenv("AZURE_CONNECTION_STRING", "HostName=hub.azure.com;...")
        result = _secrets_from_env()
        assert result["comms_agent"]["azure_connection_string"] == "HostName=hub.azure.com;..."

    def test_no_env_vars_returns_empty(self, monkeypatch):
        for var in ("WATSONX_API_KEY", "WATSONX_PROJECT_ID", "KIMI_API_KEY",
                    "KAI9000_API_KEY", "MANUS_API_KEY", "CLOUD_API_KEY",
                    "AZURE_CONNECTION_STRING"):
            monkeypatch.delenv(var, raising=False)
        assert _secrets_from_env() == {}


# ---------------------------------------------------------------------------
# load_secrets — file-based
# ---------------------------------------------------------------------------

class TestLoadSecrets:
    def test_applies_file_secrets(self, tmp_path):
        secrets_yaml = tmp_path / "secrets.yaml"
        secrets_yaml.write_text(textwrap.dedent("""\
            ai_agent:
              chaimera3sp:
                providers:
                  kimi:
                    api_key: "kimi-from-file"
        """))
        config: dict = {}
        load_secrets(config, secrets_file=secrets_yaml)
        assert config["ai_agent"]["chaimera3sp"]["providers"]["kimi"]["api_key"] == "kimi-from-file"

    def test_env_overrides_file(self, tmp_path, monkeypatch):
        secrets_yaml = tmp_path / "secrets.yaml"
        secrets_yaml.write_text("ai_agent:\n  chaimera3sp:\n    providers:\n      kimi:\n        api_key: 'file-key'\n")
        monkeypatch.setenv("KIMI_API_KEY", "env-key")
        config: dict = {}
        load_secrets(config, secrets_file=secrets_yaml)
        assert config["ai_agent"]["chaimera3sp"]["providers"]["kimi"]["api_key"] == "env-key"

    def test_missing_file_no_error(self, tmp_path):
        config: dict = {"existing": "value"}
        load_secrets(config, secrets_file=tmp_path / "nonexistent.yaml")
        assert config == {"existing": "value"}

    def test_merges_without_overwriting_unrelated_keys(self, tmp_path):
        secrets_yaml = tmp_path / "secrets.yaml"
        secrets_yaml.write_text("comms_agent:\n  api_key: 'my-token'\n")
        config = {"comms_agent": {"cloud_connector": "http", "cloud_endpoint": "https://example.com"}}
        load_secrets(config, secrets_file=secrets_yaml)
        assert config["comms_agent"]["cloud_connector"] == "http"
        assert config["comms_agent"]["api_key"] == "my-token"

    def test_both_env_and_file(self, tmp_path, monkeypatch):
        secrets_yaml = tmp_path / "secrets.yaml"
        secrets_yaml.write_text(
            "ai_agent:\n  chaimera3sp:\n    providers:\n"
            "      watsonx:\n        api_key: 'wx-file'\n"
            "      kimi:\n        api_key: 'kimi-file'\n"
        )
        monkeypatch.setenv("WATSONX_API_KEY", "wx-env")
        config: dict = {}
        load_secrets(config, secrets_file=secrets_yaml)
        providers = config["ai_agent"]["chaimera3sp"]["providers"]
        assert providers["watsonx"]["api_key"] == "wx-env"   # env wins
        assert providers["kimi"]["api_key"] == "kimi-file"   # file used
