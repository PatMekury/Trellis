"""Trellis caregiver SMS dispatcher service.

FastAPI service that:
  - Stores caregiver enrollments (phone, ward, child age)
  - Reads the current forecast (the same forecast.json the dashboard uses)
  - Per ward, decides whether to send (based on tier change vs last send)
  - Dispatches via a pluggable SMS provider (mock / Africa's Talking / Twilio)
  - Logs everything to an audit table

Run locally:
  pip install fastapi uvicorn
  uvicorn app:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

HERE = Path(__file__).parent
DB_PATH = HERE / "trellis_sms.db"
FORECAST_PATH = HERE / "forecast.json"  # symlink or copy from mvp/forecast_may_2026.json

PROVIDER_NAME = os.getenv("TRELLIS_SMS_PROVIDER", "mock")  # "mock" | "africas_talking" | "twilio"


# ============ DATABASE ============

def init_db():
    with conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                lganame TEXT NOT NULL,
                wardname TEXT NOT NULL,
                child_age_years INTEGER,
                lang TEXT DEFAULT 'en',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(phone, lganame, wardname)
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                lganame TEXT NOT NULL,
                wardname TEXT NOT NULL,
                tier TEXT NOT NULL,
                message TEXT NOT NULL,
                provider TEXT NOT NULL,
                provider_response TEXT,
                sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                forecast_year INTEGER,
                forecast_month INTEGER
            );
            CREATE TABLE IF NOT EXISTS last_tier (
                lganame TEXT NOT NULL,
                wardname TEXT NOT NULL,
                tier TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'general',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (lganame, wardname, channel)
            );
        """)


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


# ============ FORECAST ============

def load_forecast():
    if not FORECAST_PATH.exists():
        return []
    return json.loads(FORECAST_PATH.read_text())


# ============ SMS PROVIDERS ============

class SmsProvider:
    name = "base"

    def send(self, phone: str, message: str) -> dict:
        raise NotImplementedError


class MockProvider(SmsProvider):
    """Logs to console; doesn't actually send. Useful for development."""
    name = "mock"

    def send(self, phone: str, message: str) -> dict:
        print(f"[mock-sms] to={phone}: {message[:80]}{'…' if len(message) > 80 else ''}")
        return {"status": "ok", "provider": "mock"}


class AfricasTalkingProvider(SmsProvider):
    """Africa's Talking — the default SMS gateway for Nigerian deployments.

    Requires env vars TRELLIS_AT_USERNAME and TRELLIS_AT_API_KEY.
    Uses sandbox by default; set TRELLIS_AT_LIVE=1 for production.
    """
    name = "africas_talking"

    def send(self, phone: str, message: str) -> dict:
        try:
            import africastalking
        except ImportError:
            return {"status": "error", "provider": "africas_talking",
                    "error": "africastalking package not installed; pip install africastalking"}
        username = os.getenv("TRELLIS_AT_USERNAME", "sandbox")
        api_key = os.getenv("TRELLIS_AT_API_KEY", "")
        if not api_key:
            return {"status": "error", "provider": "africas_talking",
                    "error": "TRELLIS_AT_API_KEY not set"}
        africastalking.initialize(username, api_key)
        sms = africastalking.SMS
        try:
            r = sms.send(message, [phone])
            return {"status": "ok", "provider": "africas_talking", "response": r}
        except Exception as e:
            return {"status": "error", "provider": "africas_talking", "error": str(e)}


class TwilioProvider(SmsProvider):
    """Twilio — used as a fallback or for testing outside Nigeria."""
    name = "twilio"

    def send(self, phone: str, message: str) -> dict:
        try:
            from twilio.rest import Client
        except ImportError:
            return {"status": "error", "provider": "twilio",
                    "error": "twilio package not installed; pip install twilio"}
        account_sid = os.getenv("TRELLIS_TWILIO_SID", "")
        auth_token = os.getenv("TRELLIS_TWILIO_TOKEN", "")
        from_num = os.getenv("TRELLIS_TWILIO_FROM", "")
        if not all([account_sid, auth_token, from_num]):
            return {"status": "error", "provider": "twilio",
                    "error": "TRELLIS_TWILIO_{SID,TOKEN,FROM} env vars must be set"}
        try:
            c = Client(account_sid, auth_token)
            m = c.messages.create(body=message, from_=from_num, to=phone)
            return {"status": "ok", "provider": "twilio", "sid": m.sid}
        except Exception as e:
            return {"status": "error", "provider": "twilio", "error": str(e)}


PROVIDERS = {p.name: p() for p in (MockProvider, AfricasTalkingProvider, TwilioProvider)}


def provider() -> SmsProvider:
    return PROVIDERS.get(PROVIDER_NAME, PROVIDERS["mock"])


# ============ MESSAGE TEMPLATES ============
#
# Three channels of advisory text, dispatched on three independent triggers:
#   render            -> generic environmental alert tier (existing behaviour)
#   render_malaria    -> malaria-risk tier (likely / possible / watch)
#   render_respiratory -> paediatric respiratory exposure (high NO2 + under-5 caregivers)
#
# Each renderer emits English (default) or Nigerian Pidgin ("pcm") versions.

def render(tier: str, ward: str, lang: str = "en") -> str:
    if lang == "pcm":  # Nigerian Pidgin
        if tier == "likely":
            return (f"TRELLIS WARN: {ward}. Air bad small-small for next 4 weeks. "
                    f"Make small pikin no dey play outside between 11am-3pm. "
                    f"If pikin dey cough or breath fast, take am go health centre quick. Free advice: 1234.")
        if tier == "possible":
            return (f"TRELLIS NOTICE: {ward}. Air go fit be bad next 4 weeks. "
                    f"Pikin wey get asthma make e carry inhaler. Open window for morning. Free advice: 1234.")
        return (f"TRELLIS UPDATE: {ward}. Air dey okay for now. We go message you again if e change. Free: 1234.")
    # English (default)
    if tier == "likely":
        return (f"TRELLIS ALERT: {ward}. Air quality LIKELY to be poor next 2-4 weeks. "
                f"Keep small children indoors mid-day. Watch for cough or fast breathing. "
                f"Visit PHC if breathing fast. Free advice line: 1234.")
    if tier == "possible":
        return (f"TRELLIS NOTICE: {ward}. POSSIBLE poor air next 2-4 weeks. "
                f"Children with asthma carry inhaler. Open windows morning, close noon. Free advice: 1234.")
    return (f"TRELLIS UPDATE: {ward}. Air WATCH this week. No immediate action. "
            f"Trellis will message if conditions change. Free advice: 1234.")


def render_malaria(tier: str, ward: str, lang: str = "en") -> str:
    """Malaria-risk advisory: rainfall + temperature thresholds, EPIDEMIA-aligned."""
    if lang == "pcm":
        if tier == "likely":
            return (f"TRELLIS MALARIA WARN: {ward}. Mosquito breeding fit high next 4 weeks. "
                    f"Sleep under net every night. If pikin get fever, go health centre to test. "
                    f"Don't keep stagnant water near house. Free advice: 1234.")
        if tier == "possible":
            return (f"TRELLIS MALARIA NOTICE: {ward}. Conditions fit support mosquito small-small. "
                    f"Use net for pikin. Cover water containers. Test for malaria if fever pass two days. Free: 1234.")
        return (f"TRELLIS MALARIA UPDATE: {ward}. Risk low now. Keep using net. Free advice: 1234.")
    # English
    if tier == "likely":
        return (f"TRELLIS MALARIA ALERT: {ward}. Environmental conditions LIKELY for mosquito breeding next 2-4 weeks. "
                f"Use ITN every night. If your child has fever, go to PHC for malaria test. "
                f"Empty containers that hold water. Free advice line: 1234.")
    if tier == "possible":
        return (f"TRELLIS MALARIA NOTICE: {ward}. Conditions POSSIBLY support mosquito breeding next 2-4 weeks. "
                f"Sleep under ITN. Cover water containers. Test for malaria if fever lasts 2 days. Free: 1234.")
    return (f"TRELLIS MALARIA UPDATE: {ward}. Risk currently low. Maintain ITN use. Free advice: 1234.")


def render_respiratory(tier: str, ward: str, lang: str = "en", child_age_years: Optional[int] = None) -> str:
    """Paediatric respiratory advisory targeted at caregivers of toddlers / under-5s.

    Rooted in the toddler-asthma framing: high-NO2 days require keeping young
    children's exposure low and managing diagnosed asthma proactively.
    """
    is_toddler = (child_age_years is not None and child_age_years <= 3)
    age_phrase_en = "toddler" if is_toddler else "child"
    age_phrase_pcm = "small pikin" if is_toddler else "pikin"

    if lang == "pcm":
        if tier == "likely":
            return (f"TRELLIS LUNGS WARN: {ward}. Air for around get high NO2. "
                    f"Make {age_phrase_pcm} no go outside for noon time. "
                    f"If pikin dey wheeze or breath fast, follow asthma plan, give blue inhaler. "
                    f"Go health centre quick if breath no come back normal. Free advice: 1234.")
        if tier == "possible":
            return (f"TRELLIS LUNGS NOTICE: {ward}. Air fit no good for pikin lungs next 2-4 weeks. "
                    f"Pikin wey dey use inhaler make e carry am. Open window for morning, close for afternoon. Free: 1234.")
        return (f"TRELLIS LUNGS UPDATE: {ward}. Air dey okay for pikin. Free advice: 1234.")
    # English
    if tier == "likely":
        return (f"TRELLIS RESPIRATORY ALERT: {ward}. Forecast NO2 LIKELY elevated for under-5s next 2-4 weeks. "
                f"Keep your {age_phrase_en} indoors during midday (11am-3pm). "
                f"If your child has diagnosed asthma, follow their action plan; have reliever inhaler ready. "
                f"Visit PHC immediately if wheeze or fast breathing does not settle. Free advice: 1234.")
        # Small note: the toddler-asthma framing is most acute below age 3.
    if tier == "possible":
        return (f"TRELLIS RESPIRATORY NOTICE: {ward}. Air may be unhealthy for under-5s next 2-4 weeks. "
                f"If your {age_phrase_en} uses an inhaler, carry it. Open windows in cool morning, close midday. Free: 1234.")
    return (f"TRELLIS RESPIRATORY UPDATE: {ward}. Air healthy for under-5s currently. Free advice: 1234.")


# ============ FASTAPI ============

app = FastAPI(title="Trellis SMS dispatcher", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def _startup():
    init_db()


# ----- Models -----

class EnrollmentIn(BaseModel):
    phone: str = Field(..., description="E.164 format phone number, e.g. +2348012345678")
    lganame: str
    wardname: str
    child_age_years: Optional[int] = None
    lang: str = Field("en", pattern=r"^(en|pcm)$")


class EnrollmentOut(EnrollmentIn):
    id: int
    created_at: str


class AuditEntry(BaseModel):
    id: int
    phone: str
    lganame: str
    wardname: str
    tier: str
    message: str
    provider: str
    provider_response: Optional[str]
    sent_at: str
    forecast_year: int
    forecast_month: int


class DispatchResult(BaseModel):
    sent: int
    skipped: int
    failed: int
    details: list[dict]


# ----- Endpoints -----

@app.get("/")
def root():
    return {
        "service": "trellis-sms",
        "provider": PROVIDER_NAME,
        "forecast_loaded": FORECAST_PATH.exists(),
        "endpoints": ["/forecast", "/enroll", "/enrollments", "/dispatch", "/audit"],
    }


@app.get("/forecast")
def get_forecast():
    return load_forecast()


@app.post("/enroll", response_model=EnrollmentOut)
def enroll(e: EnrollmentIn):
    with conn() as c:
        try:
            cur = c.execute(
                "INSERT INTO enrollments (phone, lganame, wardname, child_age_years, lang) "
                "VALUES (?, ?, ?, ?, ?) RETURNING id, created_at",
                (e.phone, e.lganame, e.wardname, e.child_age_years, e.lang),
            )
            row = cur.fetchone()
        except sqlite3.IntegrityError:
            raise HTTPException(409, "phone already enrolled for this ward")
    return EnrollmentOut(id=row["id"], created_at=row["created_at"], **e.model_dump())


@app.get("/enrollments")
def list_enrollments(lganame: Optional[str] = None, wardname: Optional[str] = None):
    sql = "SELECT * FROM enrollments WHERE 1=1"
    args = []
    if lganame:
        sql += " AND lganame = ?"; args.append(lganame)
    if wardname:
        sql += " AND wardname = ?"; args.append(wardname)
    with conn() as c:
        rows = [dict(r) for r in c.execute(sql, args).fetchall()]
    return rows


@app.post("/dispatch")
def dispatch(
    only_changed: bool = Query(True, description="Only send when ward tier has changed since last send"),
    only_alert: bool = Query(True, description="Only send for likely or possible (skip watch)"),
    channel: str = Query("general", description="Which advisory channel: general | malaria | respiratory"),
) -> DispatchResult:
    """Run a dispatch cycle: read forecast, send SMS to enrolled caregivers per the policy.

    The channel parameter selects the advisory text and the tier source:
      general     -> uses forecast['tier'] (existing environmental alert tier)
      malaria     -> uses forecast['malaria_risk_tier']
      respiratory -> uses forecast['tier'] (NO2-driven), with toddler-asthma framing
    """
    if channel not in ("general", "malaria", "respiratory"):
        raise HTTPException(400, "channel must be one of general, malaria, respiratory")
    forecast = load_forecast()
    if not forecast:
        raise HTTPException(503, "no forecast available")

    fc_by_ward = {f"{f['lganame']}|{f['wardname']}": f for f in forecast}
    sent = skipped = failed = 0
    details = []

    # The last_tier table is partitioned by channel so that, e.g., a malaria
    # transition does not suppress a respiratory dispatch on the same ward.
    tier_field = {"general": "tier", "malaria": "malaria_risk_tier", "respiratory": "tier"}[channel]

    with conn() as c:
        last_tiers = {(r["lganame"], r["wardname"]): r["tier"]
                      for r in c.execute(
                          "SELECT * FROM last_tier WHERE channel = ? OR channel IS NULL",
                          (channel,),
                      ).fetchall()}
        enrolls = c.execute("SELECT * FROM enrollments").fetchall()

        for e in enrolls:
            key = f"{e['lganame']}|{e['wardname']}"
            f = fc_by_ward.get(key)
            if not f:
                skipped += 1
                details.append({"phone": e["phone"], "reason": "no forecast for ward"})
                continue
            tier = f.get(tier_field, "watch")

            if only_alert and tier == "watch":
                skipped += 1
                continue
            prev = last_tiers.get((e["lganame"], e["wardname"]))
            if only_changed and prev == tier:
                skipped += 1
                continue

            if channel == "malaria":
                msg = render_malaria(tier, e["wardname"], e["lang"] or "en")
            elif channel == "respiratory":
                # sqlite3.Row doesn't expose .get(); access the column directly.
                # child_age_years is nullable in the schema, so e["child_age_years"] may be None.
                msg = render_respiratory(tier, e["wardname"], e["lang"] or "en", e["child_age_years"])
            else:
                msg = render(tier, e["wardname"], e["lang"] or "en")
            res = provider().send(e["phone"], msg)
            ok = res.get("status") == "ok"

            c.execute(
                "INSERT INTO audit (phone, lganame, wardname, tier, message, provider, "
                "provider_response, forecast_year, forecast_month) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (e["phone"], e["lganame"], e["wardname"], tier, msg, provider().name,
                 json.dumps(res), f.get("forecast_year"), f.get("forecast_month")),
            )
            if ok:
                sent += 1
            else:
                failed += 1
            details.append({"phone": e["phone"], "ward": e["wardname"], "tier": tier,
                            "ok": ok, "msg_len": len(msg)})

        # Update last_tier for every ward we have a forecast for, on the
        # channel we just dispatched. Other channels keep their own state.
        for f in forecast:
            c.execute(
                "INSERT OR REPLACE INTO last_tier (lganame, wardname, tier, channel, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (f["lganame"], f["wardname"], f.get(tier_field, "watch"), channel,
                 datetime.now(timezone.utc).isoformat()),
            )

    return DispatchResult(sent=sent, skipped=skipped, failed=failed, details=details)


@app.get("/audit")
def list_audit(limit: int = 100):
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM audit ORDER BY sent_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


@app.delete("/enroll/{enrollment_id}")
def unenroll(enrollment_id: int):
    with conn() as c:
        cur = c.execute("DELETE FROM enrollments WHERE id = ?", (enrollment_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "not found")
    return {"deleted": enrollment_id}
