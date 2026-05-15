"""Tests for the Trellis MCP server.

Run from the repository root:
    pip install pytest httpx mcp
    cd mcp
    PYTHONPATH=. pytest tests/ -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _import_server():
    sys.path.insert(0, str(REPO_ROOT / "mcp"))
    if "server" in sys.modules:
        del sys.modules["server"]
    try:
        import server  # noqa: F401

        return server
    except SystemExit:
        # The mcp package is not installed; raise SystemExit per the module's
        # `raise SystemExit(1)` block. Skip the runtime tests in that case.
        pytest.skip("mcp package not installed; pip install mcp")


def test_module_imports():
    server = _import_server()
    assert hasattr(server, "server")
    assert callable(server.tool_forecast)
    assert callable(server.tool_alert_list)
    assert callable(server.tool_priority_score)
    assert callable(server.tool_send_advisory)
    assert callable(server.tool_ward_profile)


@pytest.mark.asyncio
async def test_get_forecast_falls_back_to_local(monkeypatch):
    """When backend unreachable, the helper falls back to the local JSON file."""
    server = _import_server()
    monkeypatch.setattr(server, "BACKEND", "http://nowhere.invalid")
    # Local fallback is bundled with the repo
    fc = await server.get_forecast()
    assert isinstance(fc, list)
    if fc:
        # At least the standard schema fields are present
        assert "lganame" in fc[0]
        assert "wardname" in fc[0]


@pytest.mark.asyncio
async def test_alert_list_filters_by_tier(monkeypatch):
    server = _import_server()

    # Stub the forecast loader with a deterministic small list
    async def stub_forecast():
        return [
            {"lganame": "A", "wardname": "X", "tier": "likely", "no2_forecast_umol_m2": 30},
            {"lganame": "A", "wardname": "Y", "tier": "possible", "no2_forecast_umol_m2": 22},
            {"lganame": "A", "wardname": "Z", "tier": "watch", "no2_forecast_umol_m2": 14},
        ]

    monkeypatch.setattr(server, "get_forecast", stub_forecast)
    out = await server.tool_alert_list({"tier": "alert", "limit": 10})
    import json

    parsed = json.loads(out[0].text)
    # alert = likely + possible
    assert parsed["n_results"] == 2
    assert {w["wardname"] for w in parsed["wards"]} == {"X", "Y"}


@pytest.mark.asyncio
async def test_priority_score_normalises_weights(monkeypatch):
    server = _import_server()

    # Stub minimal data
    async def stub_forecast():
        return [{"lganame": "A", "wardname": "X", "no2_forecast_umol_m2": 30}]

    async def stub_profiles():
        return {"A|X": {"lga": "A", "ward": "X", "pop_under5": 5000, "flare_bcm": 0.5, "fac_phc": 2}}

    monkeypatch.setattr(server, "get_forecast", stub_forecast)
    monkeypatch.setattr(server, "get_ward_profiles", stub_profiles)
    out = await server.tool_priority_score(
        {
            "weight_child": 1.0,
            "weight_no2": 0.0,
            "weight_coverage_gap": 0.0,
            "weight_flare": 0.0,
        }
    )
    import json

    parsed = json.loads(out[0].text)
    weights = parsed["weights_used"]
    # Weights should sum to ~1.0 after normalisation
    total = weights["child"] + weights["no2"] + weights["coverage_gap"] + weights["flare"]
    assert abs(total - 1.0) < 1e-9
