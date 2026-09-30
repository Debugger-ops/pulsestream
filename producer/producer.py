"""
Publishes events onto the Kafka `raw-events` topic.

Every downstream service only cares that JSON with a "text" field lands on the
topic, so the source is pluggable:

    python3 producer/producer.py                      # replay data/holdout.csv on a loop (default)
    python3 producer/producer.py --rate 5             # 5 events / second
    python3 producer/producer.py --source rss --url https://hnrss.org/newest
    python3 producer/producer.py --source webhook --port 9000
        curl -X POST localhost:9000/ticket -H 'content-type: application/json' \
             -d '{"text": "I was charged twice"}'
    echo "how do I reset my password" | python3 producer/producer.py --source stdin
"""
import argparse
import csv
import itertools
import json
import random
import sys
import threading
import time
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from kafka_utils import make_producer


def make_event(text: str, source: str) -> dict:
    return {"id": uuid.uuid4().hex[:12], "text": text.strip(), "ts": time.time(), "source": source}


# ---------------------------------------------------------------- sources
def csv_source(_args):
    path = config.ROOT / "data" / "holdout.csv"   # unseen sentences, not the training set
    with open(path, newline="", encoding="utf-8") as f:
        texts = [r["text"] for r in csv.DictReader(f)]
    while True:
        random.shuffle(texts)
        yield from texts


def rss_source(args):
    """Polls an RSS/Atom feed and yields the title of each new item once."""
    seen = set()
    while True:
        try:
            with urllib.request.urlopen(args.url, timeout=10) as r:
                root = ET.fromstring(r.read())
            titles = [t.text for t in root.iter() if t.tag.endswith("title") and t.text][1:]
            for title in titles:
                if title not in seen:
                    seen.add(title)
                    yield title
        except Exception as e:                      # network hiccup: log and keep going
            print(f"[rss] poll failed: {e}")
        time.sleep(args.poll)


def stdin_source(_args):
    for line in sys.stdin:
        if line.strip():
            yield line


def webhook_source(args):
    """Runs a tiny HTTP server; every POST /ticket {"text": ...} becomes an event."""
    import queue
    q = queue.Queue()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
                q.put(body["text"])
                self.send_response(202)
            except Exception:
                self.send_response(400)
            self.end_headers()

        def log_message(self, *a):
            pass

    server = HTTPServer(("0.0.0.0", args.port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"webhook listening on http://localhost:{args.port}/ticket")
    while True:
        yield q.get()


SOURCES = {"csv": csv_source, "rss": rss_source, "stdin": stdin_source, "webhook": webhook_source}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=SOURCES, default="csv")
    ap.add_argument("--rate", type=float, default=1.0, help="events per second (csv source)")
    ap.add_argument("--url", default="https://hnrss.org/newest", help="feed URL (rss source)")
    ap.add_argument("--poll", type=float, default=30, help="seconds between feed polls (rss source)")
    ap.add_argument("--port", type=int, default=9000, help="listen port (webhook source)")
    args = ap.parse_args()

    producer = make_producer("producer")
    print(f"source={args.source} -> topic '{config.RAW_TOPIC}' (ctrl-c to stop)")
    delay = 1.0 / args.rate if args.source == "csv" else 0

    try:
        for n, text in enumerate(SOURCES[args.source](args)):
            event = make_event(text, args.source)
            producer.send(config.RAW_TOPIC, event)
            print(f"  sent #{n}: {event['text'][:70]}")
            if delay:
                time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        producer.flush()
        print("producer stopped")


if __name__ == "__main__":
    main()
