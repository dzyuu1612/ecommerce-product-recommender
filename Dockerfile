# Single-container image: on first boot with no volume-mounted model, the
# entrypoint generates a demo dataset and trains a champion model, then
# serves the API + storefront. Mount /app/data and /app/models to skip that
# bootstrap on subsequent runs.
#
#   docker build -t recsys-lite .
#   docker run --rm -p 8000:8000 \
#     -v recsys-lite-data:/app/data -v recsys-lite-models:/app/models \
#     recsys-lite
#
# torch is by far the largest dependency. On Linux, PyPI's default `torch`
# wheel bundles the full CUDA runtime (cuBLAS, cuDNN, NCCL, Triton, ...) which
# added ~6 GB of GPU libraries this image can never use -- it serves a CPU-only
# model. Installing torch first from PyTorch's CPU-only index avoids all of
# that; the subsequent `pip install -e .` then sees the requirement already
# satisfied and does not pull the CUDA build.

FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY web ./web
COPY scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh

RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir -e . \
    && chmod +x ./scripts/docker-entrypoint.sh \
    && useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data /app/models \
    && chown -R appuser:appuser /app

USER appuser

ENV RECSYS_LITE_DB_PATH=/app/data/recsys_lite.db \
    RECSYS_LITE_REGISTRY_DIR=/app/models \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
