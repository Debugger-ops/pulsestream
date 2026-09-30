# PulseStream — Real-Time Event Classifier

Real-time ML inference pipeline: events flow through Kafka, get classified by a trained model, and stream live to a React dashboard over WebSockets.

## Architecture

```
[producer] --> Kafka topic: raw-events --> [consumer + model inference] --> Kafka topic: classified-events --> [backend: FastAPI + WebSocket] --> [frontend: React dashboard]
```

## Project layout

- `producer/` — publishes events onto the `raw-events` Kafka topic (stub uses `data/sample_events.csv`; swap in a real source later — an API poll, RSS feed, support-ticket webhook, etc.)
- `model/train.py` — trains the classifier. Currently a placeholder pipeline (TF-IDF + Logistic Regression) on toy data — swap in your real dataset/labels once chosen
- `model/inference.py` — loads the trained model artifact and exposes a `predict()` function
- `consumer/consumer.py` — consumes `raw-events`, runs `predict()`, publishes results to `classified-events`
- `backend/app.py` — FastAPI service; consumes `classified-events` and broadcasts to any connected dashboard clients over WebSocket at `/ws`
- `frontend/` — React (Vite) dashboard skeleton; connects to the backend WebSocket and renders a live feed with confidence scores
- `docker-compose.yml` — single-node Kafka (KRaft mode, no Zookeeper needed) for local dev

## Setup (once you're ready to run it)

1. `docker compose up -d` — starts Kafka on `localhost:9092`
2. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
3. `python3 model/train.py` — trains on the toy `data/sample_events.csv` and saves `model/artifacts/classifier.pkl` (just to prove the pipeline works end to end)
4. `python3 consumer/consumer.py` (new terminal)
5. `python3 producer/producer.py` (new terminal)
6. `uvicorn backend.app:app --reload --port 8000` (new terminal)
7. `cd frontend && npm install && npm run dev` — opens the dashboard at localhost:5173

## Still to decide / do

- [ ] Pick the real data source + labels (support tickets? news headlines? something related to the entity-resolution hackathon?)
- [ ] Decide the real classifier (sentence-transformer embeddings + linear head vs. a small fine-tuned transformer)
- [ ] Replace `producer/producer.py`'s CSV stub with the real feed
- [ ] Design the actual dashboard UI — the current one is a bare placeholder, this is where your UX strength should show
- [ ] Add reconnect/error handling on the WebSocket client
- [ ] Write up final README with real results + a short architecture diagram/GIF for your portfolio page
