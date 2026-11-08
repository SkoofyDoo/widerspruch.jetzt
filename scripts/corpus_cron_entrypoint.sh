#!/bin/sh
set -e
cd /app

if [ "${CORPUS_CRON_RUN_ON_START:-false}" = "true" ]; then
  echo "[corpus-cron] CORPUS_CRON_RUN_ON_START=true → running update once"
  python /app/scripts/update_corpus.py || echo "[corpus-cron] initial update failed (will retry on schedule)"
fi

exec supercronic -passthrough-logs /app/scripts/corpus.crontab
