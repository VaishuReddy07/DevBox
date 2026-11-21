import os

from redis import Redis

from .config import Session, engine
from .models import Base, Event, Notification, OutboxMessage


def reset():
    Base.metadata.create_all(engine)
    with Session.begin() as db:
        db.query(Notification).delete()
        db.query(OutboxMessage).delete()
        db.query(Event).delete()
    cache = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    for key in cache.scan_iter("event:*"):
        cache.delete(key)
    cache.close()


if __name__ == "__main__":
    reset()
