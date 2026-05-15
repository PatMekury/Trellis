"""Trellis sensor simulator.

Posts realistic synthetic readings to the backend as if it were a deployed node.
Used for development and end-to-end testing.

Usage:
    python3 simulate_sensor.py --enroll
    python3 simulate_sensor.py --send 10
"""

import argparse
import hashlib
import hmac
import json
import random
import time
from datetime import UTC, datetime, timedelta

import requests

BACKEND = "http://localhost:8001"
SENSOR_ID = "TR-06"
SENSOR_SECRET = "dev-secret-tr06"
SENSOR_LAT = 5.5347
SENSOR_LON = 5.7639  # Roughly Ekurede (Warri South), the flagship demo ward


def hmac_sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def enroll():
    payload = {
        "sensor_id": SENSOR_ID,
        "channel": "PHC",
        "latitude": SENSOR_LAT,
        "longitude": SENSOR_LON,
        "secret": SENSOR_SECRET,
        "cal_pm25_a": 0.95,
        "cal_pm25_b": 1.5,
        "cal_no2_a": 1.02,
        "cal_no2_b": 0.0,
    }
    r = requests.post(f"{BACKEND}/sensors", json=payload, timeout=10)
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))


def send(n=10):
    """Send n synthetic minute-readings ending now."""
    now = datetime.now(UTC)
    readings = []
    for i in range(n):
        t = now - timedelta(minutes=n - i)
        # Realistic ranges for Niger Delta urban PHC
        readings.append(
            {
                "observed_at": t.isoformat(),
                "pm25_raw": round(random.gauss(28, 4), 1),
                "pm10_raw": round(random.gauss(48, 6), 1),
                "no2_raw": round(random.gauss(22, 3), 1),
                "temperature_c": round(random.gauss(28, 0.5), 2),
                "humidity_pct": round(random.gauss(82, 3), 1),
                "pressure_hpa": round(random.gauss(1011, 0.4), 2),
            }
        )
    payload = {"sensor_id": SENSOR_ID, "readings": readings}
    body = json.dumps(payload).encode()
    sig = hmac_sign(body, SENSOR_SECRET)
    r = requests.post(
        f"{BACKEND}/ingest",
        data=body,
        headers={"Content-Type": "application/json", "X-Signature": sig},
        timeout=10,
    )
    r.raise_for_status()
    print(f"Sent {n} readings:", r.json())


def query():
    r = requests.get(f"{BACKEND}/sensors/{SENSOR_ID}/readings?limit=5", timeout=10)
    r.raise_for_status()
    rows = r.json()
    print(f"Last 5 readings for {SENSOR_ID}:")
    for row in rows:
        print(
            f"  {row['observed_at']}  pm25_raw={row['pm25_raw']}  pm25_cal={row['pm25']:.2f}  no2_cal={row['no2']:.2f}"
        )


def ward_current():
    r = requests.get(f"{BACKEND}/wards/Warri%20South/Ekurede/current", timeout=10)
    r.raise_for_status()
    print("Ward current (Warri South / Ekurede):", json.dumps(r.json(), indent=2, default=str))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--enroll", action="store_true")
    parser.add_argument("--send", type=int, default=0, help="send N synthetic readings")
    parser.add_argument("--query", action="store_true")
    parser.add_argument("--ward", action="store_true")
    args = parser.parse_args()

    if args.enroll:
        enroll()
    if args.send:
        send(args.send)
    if args.query:
        query()
    if args.ward:
        ward_current()
    if not any([args.enroll, args.send, args.query, args.ward]):
        # Default: full smoke test
        print("== enroll ==")
        enroll()
        print("\n== send 5 ==")
        send(5)
        time.sleep(0.5)
        print("\n== query ==")
        query()
        print("\n== ward current ==")
        ward_current()
