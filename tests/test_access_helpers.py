from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.billing import access as access_mod
from app.utils import now_utc


@pytest.fixture()
def temp_subs(tmp_path, monkeypatch):
    subs = tmp_path / "subscriptions.json"
    events = tmp_path / "stripe_events.json"
    monkeypatch.setattr(access_mod, "SUBS_DB", str(subs))
    monkeypatch.setattr(access_mod, "EVENTS_DB", str(events))
    return str(subs)


def test_consume_requires_payment(temp_subs):
    with pytest.raises(HTTPException) as ei:
        access_mod.consume_use_or_402("user-1")
    assert ei.value.status_code == 402


def test_consume_decrements_credit(temp_subs):
    until = (now_utc() + timedelta(days=3)).isoformat()
    access_mod.save_subs({
        "user-1": {
            "access_until": until,
            "uses_left": 2,
            "stripe_customer_id": "",
            "last_session_id": "",
            "last_charge_id": "",
            "last_payment_intent_id": "",
            "mode": "test",
        }
    })
    rec = access_mod.consume_use_or_402("user-1")
    assert rec["uses_left"] == 1
    rec2 = access_mod.consume_use_or_402("user-1")
    assert rec2["uses_left"] == 0
    with pytest.raises(HTTPException) as ei:
        access_mod.consume_use_or_402("user-1")
    assert ei.value.status_code == 429


def test_set_user_access_adds_credit(temp_subs):
    access_mod.set_user_access("u2", days=7)
    assert access_mod.is_user_paid("u2") is True
    db = access_mod.load_subs()
    assert db["u2"]["uses_left"] == 1


def test_event_dedup(temp_subs):
    assert access_mod.dedup_event("evt_1") is False
    assert access_mod.dedup_event("evt_1") is True
