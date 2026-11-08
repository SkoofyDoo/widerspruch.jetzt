FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /usr/local/bin/uv

WORKDIR /app

ARG TARGETARCH=amd64
ARG SUPERCRONIC_VERSION=0.2.33

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && case "$TARGETARCH" in \
         amd64|arm64) SC_ARCH="$TARGETARCH" ;; \
         *) SC_ARCH=amd64 ;; \
       esac \
    && SC_URL="https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-${SC_ARCH}" \
    && python -c "import urllib.request,sys; urllib.request.urlretrieve(sys.argv[1], '/usr/local/bin/supercronic')" "$SC_URL" \
    && chmod +x /usr/local/bin/supercronic

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY src ./src
COPY ui ./ui
COPY serve.py .
COPY samples ./samples
COPY scripts ./scripts
# Prebuilt RAG index + jobcenter list (required for Railway demo without volume)
COPY data/chroma ./data/chroma
COPY data/jobcenter_de.json ./data/jobcenter_de.json

RUN sed -i 's/\r$//' ./scripts/*.sh ./scripts/corpus.crontab \
    && chmod +x ./scripts/start.sh ./scripts/corpus_cron_entrypoint.sh ./scripts/update_corpus.py

ENV PYTHONUNBUFFERED=1
ENV APP_URL=http://127.0.0.1:8008
ENV ANONYMIZED_TELEMETRY=False
ENV CHROMA_TELEMETRY=False
ENV POSTHOG_DISABLED=1
ENV EMBEDDING_PROVIDER=huggingface
ENV LLM_PROVIDER=huggingface
ENV PAYWALL_ENABLED=false
ENV DEMO_MODE=true
ENV DEMO_ALLOW_DOWNLOAD=true
ENV FULL_LETTER_PREVIEW=true

EXPOSE 8008

CMD ["./scripts/start.sh"]
