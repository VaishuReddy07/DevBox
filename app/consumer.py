import json
import logging
import os
import time

from google.cloud import pubsub_v1

from .config import Session, engine, ensure_pubsub, PROJECT
from .models import Base

log = logging.getLogger(__name__)


def run(subscription: str, handler) -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    ensure_pubsub()
    Base.metadata.create_all(engine)
    subscriber = pubsub_v1.SubscriberClient()
    path = subscriber.subscription_path(PROJECT, subscription)

    def receive(message):
        try:
            payload = json.loads(message.data.decode())
            handler(payload)
            message.ack()
        except Exception:
            log.exception("Message processing failed; leaving it for redelivery")
            message.nack()

    while True:
        try:
            subscriber.subscribe(path, callback=receive).result()
        except Exception:
            log.exception("Subscriber disconnected; reconnecting shortly")
            time.sleep(3)
