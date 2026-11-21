import logging
import json
import os
import time
from datetime import datetime, timezone

from redis import Redis
from sqlalchemy import select

from .config import PROJECT, TOPIC, Session, engine, ensure_pubsub, pubsub_client
from .models import Base, Event, OutboxMessage

cache = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)


def main():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    ensure_pubsub()
    Base.metadata.create_all(engine)
    publisher = pubsub_client()
    topic = publisher.topic_path(PROJECT, TOPIC)
    while True:
        now = datetime.now(timezone.utc)
        with Session.begin() as db:
            due = db.scalars(select(Event).where(Event.status == "scheduled", Event.scheduled_at <= now).limit(100)).all()
            for event in due:
                message = {"id": event.id, "kind": event.kind, "payload": json.loads(event.payload), "created_at": event.created_at.isoformat()}
                db.add(OutboxMessage(event_id=event.id, payload=json.dumps(message, separators=(",", ":"))))
                event.status = "accepted"
        for event in due:
            try:
                cache.delete(f"event:{event.id}")
            except Exception:
                logging.exception("Could not invalidate scheduled event cache %s", event.id)
        with Session() as db:
            pending = db.scalars(select(OutboxMessage).where(OutboxMessage.published_at.is_(None)).order_by(OutboxMessage.id).limit(100)).all()
            batch = [(row.id, row.event_id, row.payload) for row in pending]
        for row_id, event_id, payload in batch:
            try:
                publisher.publish(topic, payload.encode(), event_id=event_id).result(timeout=10)
                with Session.begin() as db:
                    row = db.get(OutboxMessage, row_id)
                    if row and row.published_at is None:
                        row.published_at = datetime.now(timezone.utc)
                        row.attempts += 1
            except Exception:
                with Session.begin() as db:
                    row = db.get(OutboxMessage, row_id)
                    if row:
                        row.attempts += 1
                logging.exception("Could not publish outbox event %s", event_id)
        time.sleep(2)


if __name__ == "__main__":
    main()
