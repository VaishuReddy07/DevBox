import os
import time

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql+psycopg://devbox:devbox_local_only@localhost:5432/devbox")


engine = create_engine(database_url(), pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)
PROJECT = os.getenv("PUBSUB_PROJECT_ID", "devbox-local")
TOPIC = "activity-events"
SUBSCRIPTIONS = ("activity-worker", "activity-notifier")


def pubsub_client():
    return pubsub_v1.PublisherClient()


def ensure_pubsub() -> None:
    publisher = pubsub_client()
    topic_path = publisher.topic_path(PROJECT, TOPIC)
    for attempt in range(30):
        try:
            try:
                publisher.create_topic(request={"name": topic_path})
            except AlreadyExists:
                pass
            subscriber = pubsub_v1.SubscriberClient()
            for name in SUBSCRIPTIONS:
                path = subscriber.subscription_path(PROJECT, name)
                try:
                    subscriber.create_subscription(request={"name": path, "topic": topic_path, "ack_deadline_seconds": 30})
                except AlreadyExists:
                    pass
            subscriber.close()
            return
        except Exception:
            if attempt == 29:
                raise
            time.sleep(1)
