FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# Build context is the repo root. We keep the repo layout inside the container
# (/srv/chmabapos_api) because config.py resolves chmabapos_api/.env relative
# to the working directory.
COPY chmabapos_api /srv/chmabapos_api

RUN pip install --no-cache-dir -r /srv/chmabapos_api/requirements.txt

EXPOSE 8000

# Apply pending migrations, seed reference data (currencies/plans), then start.
CMD ["sh", "-c", "alembic -c chmabapos_api/alembic.ini upgrade head && python chmabapos_api/scripts/seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir chmabapos_api"]
