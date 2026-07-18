"""
Backward-compatible entrypoint.

Prefer:
  uvicorn app.main:app --host 0.0.0.0 --port 8008

This shim keeps older commands working:
  uvicorn serve:app --port 8008
"""

from app.main import app

__all__ = ["app"]
