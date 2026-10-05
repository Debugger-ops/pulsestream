# One small image runs both the consumer and the backend (the compose file picks the command).
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY config.py kafka_utils.py ./
COPY backend ./backend
COPY consumer ./consumer
COPY model ./model
COPY data ./data
EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
