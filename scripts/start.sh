#!/bin/sh
set -e
# Railway/Render inject PORT; never hardcode only 8008 for public proxy
PORT="${PORT:-8008}"
echo "Starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers --forwarded-allow-ips='*'
