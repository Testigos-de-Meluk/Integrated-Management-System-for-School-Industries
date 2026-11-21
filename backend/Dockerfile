# Backend image (Django + Celery). The same image runs the API, the Celery worker and Celery Beat;
# only the command changes (see docker-compose.yml).
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser

# --- Development target: includes test and lint tooling; code is bind-mounted by Compose --------
FROM base AS dev

COPY requirements/ requirements/
RUN pip install -r requirements/dev.txt

COPY . .

USER appuser
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
