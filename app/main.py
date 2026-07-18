"""
FastAPI application entrypoint.

Run:
  uvicorn app.main:app --host 0.0.0.0 --port 8008 --reload
"""

from __future__ import annotations

import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import UI_DIR
from app.routes import billing, feedback, health, pages, search, tester, widerspruch

app = FastAPI(
    title="WIDERSPRUCH.JETZT API",
    description=(
        "RAG-assisted formal Widerspruch drafts for German Jobcenter decisions "
        "(SGB II + SGB X). Document assistance only — not legal advice."
    ),
    version="1.0.0",
)

if UI_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")

app.include_router(pages.router)
app.include_router(health.router)
app.include_router(search.router)
app.include_router(widerspruch.router)
app.include_router(tester.router)
app.include_router(billing.router)
app.include_router(feedback.router)


@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    print("=== EXCEPTION ===")
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": str(exc)})
