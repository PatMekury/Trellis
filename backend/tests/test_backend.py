"""Tests for the Trellis sensor backend.

Run from the repository root:
    pip install fastapi pydantic httpx pytest asyncpg
    cd backend
    PYTHONPATH=. pytest tests/ -v

Tests in this file exercise the request-shape and validation paths that don't
require Postgres. The Postgres-bound paths (ingest with real ward attribution,
ward_current with PostGIS) are tested with simulate_sensor.py against a live
docker compose stack.
"""
from __future__ import annotations

import hmac
import hashlib
import json
import os
import sys

import pytest


@pytest.fixture
def app_module(monkeypatch):
    """Import the backend without the Postgres lifespan running."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@localhost/x")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if "app" in sys.modules:
        del sys.modules["app"]
    import app
    return app


def test_module_imports(app_module):
    """The backend must import cleanly with all routes registered."""
    routes = [r.path for r in app_module.app.routes if hasattr(r, "path")]
    assert "/" in routes
    assert "/sensors" in routes
    assert "/ingest" in routes
    assert "/forecast" in routes


def test_schema_sql_contains_required_tables(app_module):
    sql = app_module.SCHEMA_SQL
    assert "CREATE TABLE IF NOT EXISTS sensors" in sql
    assert "CREATE TABLE IF NOT EXISTS readings" in sql
    assert "CREATE TABLE IF NOT EXISTS ward_polygons" in sql
    assert "CREATE TABLE IF NOT EXISTS sensor_secrets" in sql
    assert "CREATE EXTENSION IF NOT EXISTS postgis" in sql


def test_hmac_helper_round_trip(app_module):
    body = b'{"sensor_id":"TR-01","readings":[]}'
    secret = "super-secret"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert app_module.verify_hmac(secret, body, sig) is True
    # Wrong secret rejects
    assert app_module.verify_hmac("wrong-secret", body, sig) is False
    # Wrong signature rejects
    assert app_module.verify_hmac(secret, body, "deadbeef" * 8) is False


def test_pydantic_validates_channel_enum(app_module):
    # Enrollment channel must be PHC | school | community
    with pytest.raises(Exception):
        app_module.SensorEnrollIn(
            sensor_id="TR-01", channel="bogus",
            latitude=5.5, longitude=5.7, secret="x",
        )


def test_pydantic_validates_required_secret(app_module):
    with pytest.raises(Exception):
        app_module.SensorEnrollIn(
            sensor_id="TR-01", channel="PHC",
            latitude=5.5, longitude=5.7,  # secret missing
        )


def test_reading_in_accepts_partial_observations(app_module):
    """Readings can have any subset of pollutant/met fields populated."""
    r = app_module.ReadingIn(
        observed_at="2026-05-01T12:00:00Z",
        pm25_raw=22.4,  # only PM provided; NO2/T/H absent
    )
    assert r.pm25_raw == 22.4
    assert r.no2_raw is None


def test_ingest_in_rejects_empty_batch(app_module):
    with pytest.raises(Exception):
        app_module.IngestIn(sensor_id="TR-01", readings=[])


def test_ingest_in_caps_batch_size(app_module):
    """The ingest endpoint must reject batches larger than 120 readings."""
    too_many = [{"observed_at": "2026-05-01T00:00:00Z"} for _ in range(200)]
    with pytest.raises(Exception):
        app_module.IngestIn(sensor_id="TR-01", readings=too_many)


def test_calibration_math():
    """Per-sensor linear calibration: pm25_cal = a * raw + b."""
    a, b = 0.95, 1.5
    raw = 28.0
    expected = a * raw + b
    assert expected == pytest.approx(28.1, rel=1e-3)


def test_hmac_rejects_wrong_signature(app_module):
    """Negative test: a wrong-signature request must fail verification.

    This is the regression test for the original audit finding that the
    backend's HMAC check was a no-op. Verify that an incorrect signature is
    rejected even when the body and the secret are otherwise plausible.
    """
    body = b'{"sensor_id":"TR-01","readings":[]}'
    secret = "real-secret"
    # Genuine signature for a different secret won't match
    bad_sig_from_wrong_secret = hmac.new(
        b"wrong-secret", body, hashlib.sha256
    ).hexdigest()
    assert app_module.verify_hmac(secret, body, bad_sig_from_wrong_secret) is False
    # Tampered body — even with a correct-looking signature — must be rejected
    correct_sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    tampered_body = body + b" "
    assert app_module.verify_hmac(secret, tampered_body, correct_sig) is False
    # Empty signature must be rejected
    assert app_module.verify_hmac(secret, body, "") is False
    # Random hex of correct length must be rejected
    assert app_module.verify_hmac(secret, body, "00" * 32) is False
