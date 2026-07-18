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

ENV PYTHONUNBUFFERED=1
ENV APP_URL=http://127.0.0.1:8008

EXPOSE 8008

# Mount ./data for chroma index + runtime JSON stores
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]
