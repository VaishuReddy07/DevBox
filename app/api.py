import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .config import Session, engine, ensure_pubsub
from .models import Base, Event, Notification, OutboxMessage

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_pubsub()
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="DevBox Events API", version="1.0.0", lifespan=lifespan)
cache = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)


class EventInput(BaseModel):
    kind: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    payload: dict


class ScheduledEventInput(EventInput):
    scheduled_at: datetime


def existing_idempotent_event(key: str | None, body: EventInput, scheduled_at: datetime | None = None):
    if not key:
        return None
    with Session() as db:
        event = db.scalar(select(Event).where(Event.request_key == key))
    if event is None:
        return None
    same_request = event.kind == body.kind and json.loads(event.payload) == body.payload
    if scheduled_at is not None:
        same_request = same_request and event.scheduled_at == scheduled_at
    if not same_request:
        raise HTTPException(status_code=409, detail="Idempotency-Key was already used for a different request")
    if scheduled_at is not None:
        return {"id": event.id, "status": event.status, "scheduled_at": event.scheduled_at}
    return {"id": event.id, "status": event.status, "created_at": event.created_at}


@app.get("/health")
def health():
    try:
        cache.ping()
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return {"status": "ok"}
    except Exception as exc:
        log.exception("Health check failed")
        raise HTTPException(status_code=503, detail="A required dependency is unavailable") from exc


@app.post("/events", status_code=202)
def create_event(body: EventInput, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200)):
    existing = existing_idempotent_event(idempotency_key, body)
    if existing:
        return existing
    event_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    serialized = json.dumps(body.payload, separators=(",", ":"), sort_keys=True)
    try:
        with Session.begin() as db:
            message = {"id": event_id, "kind": body.kind, "payload": body.payload, "created_at": created_at.isoformat()}
            db.add(Event(id=event_id, kind=body.kind, payload=serialized, created_at=created_at, request_key=idempotency_key))
            db.add(OutboxMessage(event_id=event_id, payload=json.dumps(message, separators=(",", ":"))))
    except IntegrityError:
        existing = existing_idempotent_event(idempotency_key, body)
        if existing:
            return existing
        raise
    return {"id": event_id, "status": "accepted", "created_at": created_at}


@app.post("/events/scheduled", status_code=202)
def schedule_event(body: ScheduledEventInput, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200)):
    event_id = str(uuid.uuid4())
    scheduled_at = body.scheduled_at
    if scheduled_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="scheduled_at must include a timezone")
    existing = existing_idempotent_event(idempotency_key, body, scheduled_at)
    if existing:
        return existing
    try:
        with Session.begin() as db:
            db.add(Event(id=event_id, kind=body.kind, payload=json.dumps(body.payload, separators=(",", ":"), sort_keys=True), status="scheduled", scheduled_at=scheduled_at, request_key=idempotency_key))
    except IntegrityError:
        existing = existing_idempotent_event(idempotency_key, body, scheduled_at)
        if existing:
            return existing
        raise
    return {"id": event_id, "status": "scheduled", "scheduled_at": scheduled_at}


@app.get("/events/{event_id}")
def get_event(event_id: str):
    cached = cache.get(f"event:{event_id}")
    if cached:
        try:
            cached_event = json.loads(cached)
            if cached_event.get("status") == "processed":
                return cached_event
        except (json.JSONDecodeError, AttributeError):
            log.warning("Discarding invalid cache entry for event %s", event_id)
        cache.delete(f"event:{event_id}")
    with Session() as db:
        event = db.get(Event, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        result = {"id": event.id, "kind": event.kind, "payload": json.loads(event.payload), "status": event.status, "created_at": event.created_at, "processed_at": event.processed_at, "scheduled_at": event.scheduled_at}
        if event.status == "processed":
            cache.setex(f"event:{event_id}", 300, json.dumps(result, default=str))
        return result


@app.get("/notifications")
def notifications():
    with Session() as db:
        rows = db.scalars(select(Notification).order_by(Notification.id.desc()).limit(100)).all()
        return [{"event_id": row.event_id, "summary": row.summary, "created_at": row.created_at} for row in rows]
