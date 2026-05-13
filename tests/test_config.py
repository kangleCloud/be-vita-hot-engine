"""Configuration loading tests."""

from __future__ import annotations

from app.core.config import Settings


def test_settings_use_expected_network_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APP_HOST", raising=False)
    monkeypatch.delenv("APP_PUBLIC_HOST", raising=False)
    monkeypatch.delenv("APP_PORT", raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_host == "0.0.0.0"
    assert settings.app_public_host == "127.0.0.1"
    assert settings.app_port == 8000


def test_settings_allow_overriding_network_values_from_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_HOST", "0.0.0.0")
    monkeypatch.setenv("APP_PUBLIC_HOST", "192.168.2.225")
    monkeypatch.setenv("APP_PORT", "19000")

    settings = Settings(_env_file=None)

    assert settings.app_host == "0.0.0.0"
    assert settings.app_public_host == "192.168.2.225"
    assert settings.app_port == 19000
