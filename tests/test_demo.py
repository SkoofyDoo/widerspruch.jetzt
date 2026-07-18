from fastapi import HTTPException
import pytest

from app import demo as demo_mod
from app import config


def test_public_config_keys():
    cfg = demo_mod.public_config()
    assert "demo_mode" in cfg
    assert "llm_provider" in cfg
    assert "payments_enabled" in cfg


def test_download_blocked_in_demo(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_ALLOW_DOWNLOAD", False)
    with pytest.raises(HTTPException) as ei:
        demo_mod.enforce_demo_download_policy(True)
    assert ei.value.status_code == 403


def test_download_allowed_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_ALLOW_DOWNLOAD", True)
    demo_mod.enforce_demo_download_policy(True)  # no raise


def test_preview_rate_limit(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_MAX_PREVIEWS_PER_IP", 2)
    monkeypatch.setattr(config, "DEMO_RATE_WINDOW_SEC", 3600)
    demo_mod._preview_hits.clear()

    class R:
        headers = {}
        client = type("C", (), {"host": "1.2.3.4"})()

    demo_mod.check_preview_rate_limit(R())
    demo_mod.check_preview_rate_limit(R())
    with pytest.raises(HTTPException) as ei:
        demo_mod.check_preview_rate_limit(R())
    assert ei.value.status_code == 429
