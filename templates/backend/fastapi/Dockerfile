FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

COPY app/ app/

FROM python:3.12-slim

RUN groupadd -g 1001 appuser && useradd -u 1001 -g appuser -m appuser

COPY --from=builder /install /usr/local
COPY --from=builder /build/app /home/appuser/app

WORKDIR /home/appuser
USER 1001

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
