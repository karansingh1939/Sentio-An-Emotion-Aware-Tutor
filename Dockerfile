FROM ghcr.io/astral-sh/uv:0.12.17 AS uv
FROM python:3.12-slim-bookworm
COPY --from=uv /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SENTIO_HOME=/app
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app
ARG ENABLE_OCR=0
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && if [ "$ENABLE_OCR" = "1" ]; then apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng; fi \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN if [ "$ENABLE_OCR" = "1" ]; then uv sync --locked --no-dev --no-install-project --extra ocr; \
    else uv sync --locked --no-dev --no-install-project; fi
COPY src ./src
COPY LICENSE ./
RUN if [ "$ENABLE_OCR" = "1" ]; then uv sync --locked --no-dev --no-editable --extra ocr; \
    else uv sync --locked --no-dev --no-editable; fi
EXPOSE 8000
CMD ["sentio", "--host", "0.0.0.0", "--port", "8000"]
