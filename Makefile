PY := .venv/bin/python

.PHONY: setup kafka train retrain stack consumer producer backend demo frontend test
setup:      ## create venv + install Python and frontend deps
	python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd frontend && npm install
kafka:      ## start Kafka
	docker compose up -d
train:      ## train model -> model/artifacts/
	$(PY) model/train.py
retrain:    ## retrain including corrections from the dashboard, then hot-reload the running backend
	$(PY) model/train.py --with-feedback
	-curl -s -X POST localhost:8000/model/reload
stack:      ## Kafka + consumer + backend in containers (run `make train` first)
	docker compose --profile app up -d --build
consumer:
	$(PY) consumer/consumer.py
producer:
	$(PY) producer/producer.py
backend:
	.venv/bin/uvicorn backend.app:app --reload --port 8000
demo:       ## backend without Kafka (fake stream) - great for UI work / recordings
	DEMO_MODE=1 .venv/bin/uvicorn backend.app:app --port 8000
frontend:
	cd frontend && npm run dev
test:
	.venv/bin/pytest -q
