from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from sqlalchemy import text

from app.database import async_session

router = APIRouter(tags=["infrastructure"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> Response:
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return Response(
            content='{"status":"ready"}',
            media_type="application/json",
            status_code=200,
        )
    except Exception:
        return Response(
            content='{"status":"not ready"}',
            media_type="application/json",
            status_code=503,
        )


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
