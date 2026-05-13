FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=18000 \
    APP_LOG_DIR=/data/logs/be-vita-hot-engine

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["sh", "-c", "set -eu; LOG_FILE=\"${APP_LOG_DIR}/be-vita-hot-engine.log\"; mkdir -p \"${APP_LOG_DIR}\"; touch \"${LOG_FILE}\"; tail -n 0 -F \"${LOG_FILE}\" & exec uvicorn app.main:app --host 0.0.0.0 --port \"${APP_PORT}\" >> \"${LOG_FILE}\" 2>&1"]