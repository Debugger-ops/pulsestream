"""Small helpers so every service connects to Kafka the same, resilient way."""
import json
import time

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

import config


def _retry(factory, what: str, attempts: int = 30, delay: float = 2.0):
    for i in range(1, attempts + 1):
        try:
            return factory()
        except NoBrokersAvailable:
            print(f"[{what}] Kafka not reachable at {config.KAFKA_BROKER} "
                  f"(attempt {i}/{attempts}) - is `docker compose up -d` running? retrying...")
            time.sleep(delay)
    raise SystemExit(f"[{what}] gave up: Kafka never became reachable at {config.KAFKA_BROKER}")


def make_producer(what: str) -> KafkaProducer:
    return _retry(lambda: KafkaProducer(
        bootstrap_servers=config.KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        retries=5,
    ), what)


def make_consumer(topic: str, group_id: str, what: str) -> KafkaConsumer:
    return _retry(lambda: KafkaConsumer(
        topic,
        bootstrap_servers=config.KAFKA_BROKER,
        group_id=group_id,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
    ), what)
