FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8055

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY assets ./assets

EXPOSE 8055

CMD gunicorn app:server --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 120
