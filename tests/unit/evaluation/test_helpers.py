"""Tests for evaluation.shared.helpers (dotenv + env resolution)."""

import os
from pathlib import Path

import pytest

from evaluation.shared.helpers import load_dotenv_from_cwd, resolve_env_vars


def test_resolve_env_vars_loads_dotenv_from_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Broker-style _VAR references must see variables from project .env in cwd."""
    env_file = tmp_path / ".env"
    env_file.write_text("BROKER_HOST_FROM_ENV=mqtt.example.com\n")
    monkeypatch.chdir(tmp_path)

    resolved = resolve_env_vars(
        {
            "SOLACE_BROKER_URL_VAR": "BROKER_HOST_FROM_ENV",
            "vpn_name": "default",
        }
    )

    assert resolved["SOLACE_BROKER_URL"] == "mqtt.example.com"
    assert resolved["vpn_name"] == "default"


def test_load_dotenv_from_cwd_applies_project_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    key = "EVAL_HELPERS_DOTENV_TEST_XYZ"
    monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(f"{key}=from_dotenv\n")
    monkeypatch.chdir(tmp_path)
    load_dotenv_from_cwd()
    assert os.environ.get(key) == "from_dotenv"
