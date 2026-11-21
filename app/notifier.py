import json

from .consumer import run
from .config import Session
from .models import Notification
from sqlalchemy import select


def notify(message):
    summary = f"{message['kind']}: {json.dumps(message['payload'], sort_keys=True)}"
    with Session.begin() as db:
        exists = db.scalar(select(Notification.id).where(Notification.event_id == message["id"]))
        if exists is None:
            db.add(Notification(event_id=message["id"], summary=summary))


if __name__ == "__main__":
    run("activity-notifier", notify)
