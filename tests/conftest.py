"""Shared test fixtures."""

from __future__ import annotations

import sys
from typing import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import Settings, get_settings
from app.main import create_app
from app.services.hot_service import get_hot_service


@pytest.fixture(autouse=True)
def configure_test_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("APP_NAME", "be-vita-hot-engine-test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("HOT_API_TOKEN", "test-token")
    monkeypatch.setenv("HOT_HTTP_TIMEOUT", "8")
    get_settings.cache_clear()
    get_hot_service.cache_clear()
    yield
    get_settings.cache_clear()
    get_hot_service.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def app() -> Generator[FastAPI, None, None]:
    application = create_app()
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
