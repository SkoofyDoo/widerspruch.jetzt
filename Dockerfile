FROM python:3.11-slim

WORKDIR /app

# System fonts for PDF export (German umlauts)
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
RUN sed -i 's/\r$//' ./scripts/start.sh && chmod +x ./scripts/start.sh

ENV PYTHONUNBUFFERED=1
ENV APP_URL=http://127.0.0.1:8008
# Do NOT bake PORT=8008 here — Railway injects PORT at runtime.
# Local default is applied in scripts/start.sh only if PORT is unset.
ENV ANONYMIZED_TELEMETRY=False
ENV CHROMA_TELEMETRY=False
ENV POSTHOG_DISABLED=1

EXPOSE 8008

CMD ["./scripts/start.sh"]
