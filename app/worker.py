import os
from datetime import datetime, timezone

from redis import Redis

from .consumer import run
from .config import Session
from .models import Event

cache = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)


def process(message):
    with Session.begin() as db:
        event = db.get(Event, message["id"])
        if event is None:
            raise ValueError(f"Unknown event {message['id']}")
        if event.status != "processed":
            event.status = "processed"
            event.processed_at = datetime.now(timezone.utc)
    cache.delete(f"event:{message['id']}")


if __name__ == "__main__":
    run("activity-worker", process)
