FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY src ./src
COPY ui ./ui
COPY serve.py .
COPY samples ./samples
COPY scripts/start.sh ./scripts/start.sh
# Prebuilt RAG index + jobcenter list (required for Railway demo without volume)
COPY data/chroma ./data/chroma
COPY data/jobcenter_de.json ./data/jobcenter_de.json

RUN sed -i 's/\r$//' ./scripts/start.sh && chmod +x ./scripts/start.sh

ENV PYTHONUNBUFFERED=1
ENV APP_URL=http://127.0.0.1:8008
ENV ANONYMIZED_TELEMETRY=False
ENV CHROMA_TELEMETRY=False
ENV POSTHOG_DISABLED=1
ENV EMBEDDING_PROVIDER=huggingface
ENV LLM_PROVIDER=huggingface
ENV DEMO_MODE=true

EXPOSE 8008

CMD ["./scripts/start.sh"]
