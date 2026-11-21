import json
from datetime import datetime, timedelta, timezone

from .config import Session, engine
from .models import Base, Event, OutboxMessage


def seed():
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    samples = [
        ("seed-user-created", "user.created", {"user_id": "user-001", "name": "Jordan Lee"}, "accepted", now - timedelta(minutes=5)),
        ("seed-access-granted", "access.granted", {"user_id": "user-001", "resource": "reports"}, "accepted", now - timedelta(minutes=2)),
        ("seed-reminder-due", "scheduled.reminder", {"user_id": "user-001", "message": "Your access review is due"}, "scheduled", now - timedelta(seconds=10)),
        ("seed-reminder-future", "scheduled.reminder", {"user_id": "user-002", "message": "Upcoming access review"}, "scheduled", now + timedelta(days=1)),
    ]
    with Session.begin() as db:
        for event_id, kind, payload, status, scheduled_at in samples:
            if db.get(Event, event_id) is None:
                created_at = now
                serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
                db.add(Event(id=event_id, kind=kind, payload=serialized, status=status, created_at=created_at, scheduled_at=scheduled_at if status == "scheduled" else None))
                if status == "accepted":
                    message = {"id": event_id, "kind": kind, "payload": payload, "created_at": created_at.isoformat()}
                    db.add(OutboxMessage(event_id=event_id, payload=json.dumps(message, separators=(",", ":"))))


if __name__ == "__main__":
    seed()
