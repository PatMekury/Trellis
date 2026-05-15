"""Tests for the Trellis caregiver SMS dispatcher.

Run from the repository root:
    pip install fastapi pydantic httpx pytest
    cd sms
    PYTHONPATH=. pytest tests/ -v
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Spin up a fresh app instance with a temp DB and mock SMS provider per test."""
    monkeypatch.setenv("TRELLIS_SMS_PROVIDER", "mock")
    # Stub the forecast file with a known shape
    fc_path = tmp_path / "forecast.json"
    fc_path.write_text(json.dumps([
        {"lganame": "Warri South", "wardname": "Ekurede",
         "no2_forecast_umol_m2": 30.0, "no2_climatology": 23.0,
         "tier": "likely", "forecast_year": 2026, "forecast_month": 5},
        {"lganame": "Warri South", "wardname": "Ubeji",
         "no2_forecast_umol_m2": 22.0, "no2_climatology": 21.0,
         "tier": "possible", "forecast_year": 2026, "forecast_month": 5},
        {"lganame": "Bomadi", "wardname": "Bomadi",
         "no2_forecast_umol_m2": 14.0, "no2_climatology": 14.5,
         "tier": "watch", "forecast_year": 2026, "forecast_month": 5},
    ]))
    # Need to import after env is set so module-level constants pick it up
    import importlib
    import sys
    # Force reimport so DB_PATH resets
    if "app" in sys.modules:
        del sys.modules["app"]
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import app as sms_app
    sms_app.DB_PATH = str(tmp_path / "test.db")
    sms_app.FORECAST_PATH = fc_path
    sms_app.init_db()
    return TestClient(sms_app.app)


def test_root_returns_service_metadata(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "trellis-sms"
    assert "endpoints" in body


def test_enroll_then_list(client):
    r = client.post("/enroll", json={
        "phone": "+2348011110001", "lganame": "Warri South",
        "wardname": "Ekurede", "child_age_years": 3, "lang": "en",
    })
    assert r.status_code == 200, r.text
    enrollments = client.get("/enrollments").json()
    assert len(enrollments) == 1
    assert enrollments[0]["phone"] == "+2348011110001"


def test_enroll_duplicate_409(client):
    payload = {"phone": "+2348011110001", "lganame": "Warri South",
               "wardname": "Ekurede", "lang": "en"}
    assert client.post("/enroll", json=payload).status_code == 200
    # Same phone + ward → conflict
    assert client.post("/enroll", json=payload).status_code == 409


def test_enroll_invalid_lang(client):
    r = client.post("/enroll", json={
        "phone": "+2348011110001", "lganame": "Warri South",
        "wardname": "Ekurede", "lang": "fr",  # not in {en, pcm}
    })
    assert r.status_code == 422  # Pydantic validation


def test_dispatch_sends_for_alert_tiers_only_by_default(client):
    # Three caregivers, three different tiers (likely / possible / watch)
    for ward, name in [("Ekurede", "+2348011110001"),
                        ("Ubeji", "+2348011110002"),
                        ("Bomadi", "+2348011110003")]:
        lga = "Warri South" if ward in ("Ekurede", "Ubeji") else "Bomadi"
        client.post("/enroll", json={"phone": name, "lganame": lga,
                                      "wardname": ward, "lang": "en"})

    # default: only_alert=true → watch is skipped
    r = client.post("/dispatch")
    assert r.status_code == 200
    body = r.json()
    assert body["sent"] == 2  # likely + possible only
    assert body["skipped"] == 1  # the watch one


def test_dispatch_idempotent_on_unchanged_tiers(client):
    client.post("/enroll", json={"phone": "+2348011110001",
                                  "lganame": "Warri South",
                                  "wardname": "Ekurede", "lang": "en"})
    first = client.post("/dispatch").json()
    assert first["sent"] == 1
    # Second dispatch with same forecast: should skip because tier hasn't changed
    second = client.post("/dispatch").json()
    assert second["sent"] == 0
    assert second["skipped"] == 1


def test_audit_log_records_each_send(client):
    client.post("/enroll", json={"phone": "+2348011110001",
                                  "lganame": "Warri South",
                                  "wardname": "Ekurede", "lang": "en"})
    client.post("/dispatch")
    audit = client.get("/audit").json()
    assert len(audit) == 1
    row = audit[0]
    assert row["phone"] == "+2348011110001"
    assert row["wardname"] == "Ekurede"
    assert row["tier"] == "likely"
    assert row["provider"] == "mock"
    # Audit must record exactly one row per send
    assert "TRELLIS ALERT" in row["message"]


def test_pidgin_template_used_when_lang_pcm(client):
    client.post("/enroll", json={"phone": "+2348011110001",
                                  "lganame": "Warri South",
                                  "wardname": "Ekurede", "lang": "pcm"})
    client.post("/dispatch")
    audit = client.get("/audit").json()
    msg = audit[0]["message"]
    # Pidgin template starts with "TRELLIS WARN"
    assert "TRELLIS WARN" in msg or "make small pikin" in msg
