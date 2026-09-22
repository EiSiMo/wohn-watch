FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data && chown -R app:app /data /srv
USER app

# No HTTP server to probe — ask the database when the scraper last succeeded.
HEALTHCHECK --interval=120s --timeout=10s --start-period=300s --retries=3 \
    CMD ["python", "-m", "app.healthcheck"]

CMD ["python", "-m", "app.main"]
