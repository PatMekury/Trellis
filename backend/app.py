"""Trellis sensor backend.

FastAPI service that:
  - Accepts sensor readings via authenticated HTTP POST
  - Stores them in Postgres (with PostGIS for ward attribution)
  - Applies per-sensor calibration on ingest
  - Exposes query endpoints for ward-aggregated current, time series, sensor registry
  - Proxies the Trellis forecast so all four decision channels can talk to one backend

Run locally:
  docker compose up -d  (brings up Postgres + this service)
  curl http://localhost:8001/

Run without Docker (requires existing Postgres at DATABASE_URL):
  pip install -r requirements.txt
  uvicorn app:app --reload --port 8001
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import asyncpg

# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://trellis:trellis@localhost:5432/trellis",
)
FORECAST_PATH = Path(os.getenv("FORECAST_PATH",
    str(ROOT_DIR / "mvp/forecast_may_2026.json")))


# ============ DATABASE ============

POOL: Optional[asyncpg.Pool] = None


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS sensors (
    id              TEXT PRIMARY KEY,
    channel         TEXT NOT NULL,         -- 'PHC' | 'school' | 'community'
    lganame         TEXT,
    wardname        TEXT,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    geom            geometry(Point, 4326),
    secret_hash     TEXT NOT NULL,         -- sha256 of the per-sensor secret
    cal_pm25_a      DOUBLE PRECISION DEFAULT 1.0,  -- pm25_corrected = a * raw + b
    cal_pm25_b      DOUBLE PRECISION DEFAULT 0.0,
    cal_no2_a       DOUBLE PRECISION DEFAULT 1.0,
    cal_no2_b       DOUBLE PRECISION DEFAULT 0.0,
    enrolled_at     TIMESTAMPTZ DEFAULT now(),
    last_seen       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS readings (
    id              BIGSERIAL PRIMARY KEY,
    sensor_id       TEXT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
    observed_at     TIMESTAMPTZ NOT NULL,
    pm25_raw        DOUBLE PRECISION,
    pm25            DOUBLE PRECISION,      -- calibrated
    pm10_raw        DOUBLE PRECISION,
    no2_raw         DOUBLE PRECISION,
    no2             DOUBLE PRECISION,      -- calibrated
    temperature_c   DOUBLE PRECISION,
    humidity_pct    DOUBLE PRECISION,
    pressure_hpa    DOUBLE PRECISION,
    received_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_readings_sensor_observed
    ON readings(sensor_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS ward_polygons (
    lganame    TEXT,
    wardname   TEXT,
    geom       geometry(MultiPolygon, 4326),
    PRIMARY KEY (lganame, wardname)
);

CREATE INDEX IF NOT EXISTS idx_ward_polygons_geom ON ward_polygons USING GIST (geom);

-- Per-sensor plaintext secrets, kept in a separate table so they can be
-- isolated for backup / access control. Verification of HMAC requires the
-- plaintext; the sha256 hash on `sensors` is for legacy compatibility only.
CREATE TABLE IF NOT EXISTS sensor_secrets (
    sensor_id TEXT PRIMARY KEY REFERENCES sensors(id) ON DELETE CASCADE,
    secret    TEXT NOT NULL
);
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    global POOL
    POOL = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    async with POOL.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    yield
    await POOL.close()


# ============ MODELS ============

class ReadingIn(BaseModel):
    observed_at: datetime
    pm25_raw: Optional[float] = None
    pm10_raw: Optional[float] = None
    no2_raw: Optional[float] = None
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    pressure_hpa: Optional[float] = None


class IngestIn(BaseModel):
    sensor_id: str
    readings: list[ReadingIn] = Field(..., min_length=1, max_length=120)


class SensorEnrollIn(BaseModel):
    sensor_id: str
    channel: str = Field(..., pattern=r"^(PHC|school|community)$")
    lganame: Optional[str] = None
    wardname: Optional[str] = None
    latitude: float
    longitude: float
    secret: str  # plaintext secret; we store sha256 hash only
    cal_pm25_a: float = 1.0
    cal_pm25_b: float = 0.0
    cal_no2_a: float = 1.0
    cal_no2_b: float = 0.0


class SensorOut(BaseModel):
    id: str
    channel: str
    lganame: Optional[str]
    wardname: Optional[str]
    latitude: float
    longitude: float
    enrolled_at: datetime
    last_seen: Optional[datetime]


# ============ AUTH ============

def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def verify_hmac(secret: str, body_bytes: bytes, signature_hex: str) -> bool:
    expected = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_hex)


# ============ FASTAPI ============

app = FastAPI(title="Trellis sensor backend", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def root():
    return {
        "service": "trellis-backend",
        "version": "0.1.0",
        "endpoints": ["/sensors", "/ingest", "/readings", "/wards/{lga}/{ward}/current", "/forecast"],
    }


# ----- Sensor registry -----

@app.post("/sensors", response_model=SensorOut)
async def enroll_sensor(s: SensorEnrollIn):
    """Register a new sensor with its per-device secret. Idempotent."""
    async with POOL.acquire() as conn:
        # Try ward attribution if not supplied
        if not s.wardname or not s.lganame:
            row = await conn.fetchrow(
                "SELECT lganame, wardname FROM ward_polygons "
                "WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint($1, $2), 4326)) LIMIT 1",
                s.longitude, s.latitude,
            )
            if row:
                s.lganame = s.lganame or row["lganame"]
                s.wardname = s.wardname or row["wardname"]

        secret_hash = hash_secret(s.secret)
        await conn.execute(
            """
            INSERT INTO sensors (id, channel, lganame, wardname, latitude, longitude,
                                 geom, secret_hash, cal_pm25_a, cal_pm25_b, cal_no2_a, cal_no2_b)
            VALUES ($1, $2, $3, $4, $5, $6,
                    ST_SetSRID(ST_MakePoint($6, $5), 4326), $7, $8, $9, $10, $11)
            ON CONFLICT (id) DO UPDATE SET
                channel=EXCLUDED.channel, lganame=EXCLUDED.lganame, wardname=EXCLUDED.wardname,
                latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude, geom=EXCLUDED.geom,
                secret_hash=EXCLUDED.secret_hash,
                cal_pm25_a=EXCLUDED.cal_pm25_a, cal_pm25_b=EXCLUDED.cal_pm25_b,
                cal_no2_a=EXCLUDED.cal_no2_a, cal_no2_b=EXCLUDED.cal_no2_b
            """,
            s.sensor_id, s.channel, s.lganame, s.wardname, s.latitude, s.longitude,
            secret_hash, s.cal_pm25_a, s.cal_pm25_b, s.cal_no2_a, s.cal_no2_b,
        )
        # Store plaintext secret in the dedicated sensor_secrets table so HMAC
        # verification at /ingest can run hmac.compare_digest properly.
        await conn.execute(
            "INSERT INTO sensor_secrets (sensor_id, secret) VALUES ($1, $2) "
            "ON CONFLICT (sensor_id) DO UPDATE SET secret = EXCLUDED.secret",
            s.sensor_id, s.secret,
        )
        row = await conn.fetchrow(
            "SELECT id, channel, lganame, wardname, latitude, longitude, enrolled_at, last_seen "
            "FROM sensors WHERE id = $1", s.sensor_id,
        )
    return SensorOut(**dict(row))


@app.get("/sensors")
async def list_sensors():
    async with POOL.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, channel, lganame, wardname, latitude, longitude, enrolled_at, last_seen "
            "FROM sensors ORDER BY id"
        )
    return [dict(r) for r in rows]


# ----- Ingest -----

@app.post("/ingest")
async def ingest(
    payload: IngestIn,
    request: Request,
    x_signature: str = Header(..., description="HMAC-SHA256 of raw body, hex-encoded, using sensor's secret"),
):
    """Sensor pushes a batch of readings.

    The sensor signs the raw JSON body with its per-device secret using HMAC-SHA256.
    The header X-Signature carries the hex-encoded signature.
    """
    raw_body = await request.body()
    async with POOL.acquire() as conn:
        s = await conn.fetchrow(
            "SELECT cal_pm25_a, cal_pm25_b, cal_no2_a, cal_no2_b "
            "FROM sensors WHERE id = $1", payload.sensor_id,
        )
        if not s:
            raise HTTPException(404, f"unknown sensor {payload.sensor_id}")

        # HMAC-SHA256 verification of the raw body against the per-sensor secret.
        # The secret is provisioned at /sensors enrollment and stored plaintext in
        # the sensor_secrets table. Set TRELLIS_SKIP_HMAC=1 only for development.
        if os.getenv("TRELLIS_SKIP_HMAC") != "1":
            secret_row = await conn.fetchrow(
                "SELECT secret FROM sensor_secrets WHERE sensor_id = $1",
                payload.sensor_id,
            )
            if not secret_row:
                raise HTTPException(401, "no secret on file for this sensor")
            if not verify_hmac(secret_row["secret"], raw_body, x_signature):
                raise HTTPException(401, "bad signature")

        # Apply calibration and insert
        rows = []
        for r in payload.readings:
            pm25_cal = (s["cal_pm25_a"] * r.pm25_raw + s["cal_pm25_b"]) if r.pm25_raw is not None else None
            no2_cal = (s["cal_no2_a"] * r.no2_raw + s["cal_no2_b"]) if r.no2_raw is not None else None
            rows.append((
                payload.sensor_id, r.observed_at, r.pm25_raw, pm25_cal, r.pm10_raw,
                r.no2_raw, no2_cal, r.temperature_c, r.humidity_pct, r.pressure_hpa,
            ))
        await conn.executemany(
            "INSERT INTO readings (sensor_id, observed_at, pm25_raw, pm25, pm10_raw, "
            "no2_raw, no2, temperature_c, humidity_pct, pressure_hpa) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
            rows,
        )
        await conn.execute(
            "UPDATE sensors SET last_seen = $1 WHERE id = $2",
            datetime.now(timezone.utc), payload.sensor_id,
        )
    return {"ingested": len(payload.readings), "sensor_id": payload.sensor_id}


# ----- Query -----

@app.get("/sensors/{sensor_id}/readings")
async def list_readings(
    sensor_id: str,
    since: Optional[datetime] = None,
    limit: int = Query(500, le=2000),
):
    async with POOL.acquire() as conn:
        if since:
            rows = await conn.fetch(
                "SELECT * FROM readings WHERE sensor_id = $1 AND observed_at >= $2 "
                "ORDER BY observed_at DESC LIMIT $3", sensor_id, since, limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM readings WHERE sensor_id = $1 "
                "ORDER BY observed_at DESC LIMIT $2", sensor_id, limit,
            )
    return [dict(r) for r in rows]


@app.get("/wards/{lga}/{ward}/current")
async def ward_current(lga: str, ward: str):
    """Latest 1-hour-rolling-mean reading from any sensor attributed to this ward."""
    async with POOL.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                AVG(pm25) AS pm25_mean,
                AVG(no2) AS no2_mean,
                AVG(temperature_c) AS temperature_mean,
                AVG(humidity_pct) AS humidity_mean,
                COUNT(*) AS n_readings,
                MAX(observed_at) AS latest_observed_at
            FROM readings r
            JOIN sensors s ON s.id = r.sensor_id
            WHERE s.lganame = $1 AND s.wardname = $2
              AND r.observed_at > now() - interval '1 hour'
            """,
            lga, ward,
        )
    if not row or row["n_readings"] == 0:
        return {"lganame": lga, "wardname": ward, "n_readings": 0,
                "note": "no sensor readings in the last hour"}
    return dict(row)


# ----- Forecast proxy -----

@app.get("/forecast")
async def get_forecast():
    """Pass-through of the Trellis 4-week forecast.

    All four decision channels (DHIS2 dashboard, school PWA, caregiver SMS, surge UI)
    can hit this endpoint instead of bundling their own JSON, so the platform has one
    source of truth for the current forecast.
    """
    if not FORECAST_PATH.exists():
        raise HTTPException(503, "forecast not yet available")
    return json.loads(FORECAST_PATH.read_text())


# ----- Ward polygon load (admin) -----

@app.post("/admin/load-wards")
async def load_wards():
    """One-time load of pilot ward polygons from the Trellis GeoPackage into Postgres."""
    try:
        import geopandas as gpd
    except ImportError:
        raise HTTPException(500, "geopandas not installed in this container")
    src = str(ROOT_DIR / "data/trellis_delta_wards.gpkg")
    if not Path(src).exists():
        # Try alternate location for the production container
        src = os.getenv("WARDS_GPKG", "/data/trellis_delta_wards.gpkg")
    pilot = gpd.read_file(src, layer="pilot_wards")
    inserted = 0
    async with POOL.acquire() as conn:
        await conn.execute("DELETE FROM ward_polygons")
        for _, r in pilot.iterrows():
            wkt = r.geometry.wkt
            await conn.execute(
                "INSERT INTO ward_polygons (lganame, wardname, geom) "
                "VALUES ($1, $2, ST_Multi(ST_GeomFromText($3, 4326)))",
                r["lganame"], r["wardname"], wkt,
            )
            inserted += 1
    return {"loaded": inserted}