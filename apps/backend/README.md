# Kreator Backend

FastAPI service exposing CRUD over `items`, instrumented with OpenTelemetry and Prometheus.

## Local development

```bash
cp .env.example .env   # edit if your Postgres differs
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs.
