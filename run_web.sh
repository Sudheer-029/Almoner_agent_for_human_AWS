#!/usr/bin/env bash
# Start the review queue.
set -e
exec uvicorn almoner.web:app --host 0.0.0.0 --port "${PORT:-8000}"
