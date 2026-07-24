FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps needed by psycopg2, xhtml2pdf/reportlab, python-docx/pptx
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Single container app running both the API (gunicorn) and the Celery
# worker under supervisord, to fit within a single Container App's cost
# envelope. See infra/main.bicep and infra/README.md for the trade-off
# this makes against running them as separate, independently-scaled apps.
CMD ["supervisord", "-c", "supervisord.conf"]
