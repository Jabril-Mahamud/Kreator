# Kreator Backend

FastAPI service exposing CRUD over `items`, instrumented with OpenTelemetry and Prometheus.

## Local development

```bash
pip install -e .
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/kreator
alembic upgrade head
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs.
