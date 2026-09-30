"""
Consumes raw-events, classifies each with model.inference.predict(), and
publishes the enriched result to classified-events for the backend.

Output event = input event + label, confidence, top (runner-ups), latency_ms.
Bad messages (missing/empty "text", invalid JSON) are logged and skipped so a
single poison message never kills the stream.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from kafka_utils import make_consumer, make_producer
from model.inference import predict


def main():
    predict("warm up")                                   # fail fast if no model is trained
    consumer = make_consumer(config.RAW_TOPIC, "classifier", "consumer")
    producer = make_producer("consumer")
    print(f"listening on '{config.RAW_TOPIC}', classifying, forwarding to '{config.CLASSIFIED_TOPIC}'")

    handled = 0
    try:
        for msg in consumer:
            event = msg.value
            text = (event or {}).get("text", "") if isinstance(event, dict) else ""
            if not text.strip():
                print(f"  skipped malformed message at offset {msg.offset}")
                continue

            t0 = time.perf_counter()
            label, confidence, top = predict(text)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            result = {**event, "label": label, "confidence": confidence,
                      "top": top, "latency_ms": latency_ms, "classified_ts": time.time()}
            producer.send(config.CLASSIFIED_TOPIC, result)
            handled += 1
            print(f"  {event.get('id')}: {label} ({confidence:.2f}, {latency_ms}ms) -- {text[:50]}")
    except KeyboardInterrupt:
        pass
    finally:
        producer.flush()
        consumer.close()
        print(f"consumer stopped after {handled} events")


if __name__ == "__main__":
    main()
