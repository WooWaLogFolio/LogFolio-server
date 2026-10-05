FROM python:3.11.16-slim-bookworm

ARG INSTALL_EMBEDDING=false
ARG TORCH_VERSION=2.6.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=600

WORKDIR /app

RUN addgroup --system logfolio && \
    adduser --system --ingroup logfolio --home /home/logfolio logfolio && \
    mkdir -p /home/logfolio/.cache/huggingface && \
    chown -R logfolio:logfolio /home/logfolio

COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts

RUN if [ "$INSTALL_EMBEDDING" = "true" ]; then \
        python -m pip install "torch==$TORCH_VERSION" --index-url https://download.pytorch.org/whl/cpu && \
        python -m pip install '.[embedding]'; \
    else \
        python -m pip install .; \
    fi

# Evaluation profiles run versioned fixtures from inside the image.
COPY --chown=logfolio:logfolio evals ./evals

USER logfolio

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["uvicorn", "logfolio_ai.main:app", "--host", "0.0.0.0", "--port", "8000"]
