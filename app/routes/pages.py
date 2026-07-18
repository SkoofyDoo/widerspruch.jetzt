"""Static marketing / legal pages and UI entrypoints."""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.config import COLLECTION, JOB_CENTER_JSON, UI_DIR

router = APIRouter(tags=["pages"])


@router.get("/")
def root():
    # Prefer product UI when present
    index = UI_DIR / "index.html"
    if index.is_file():
        return FileResponse(str(index))
    return {
        "service": "SGB II + SGB X RAG API",
        "collection": COLLECTION,
        "docs": "/docs",
        "ui": "/ui",
    }


@router.get("/pricing")
@router.get("/pricing/")
def pricing():
    return FileResponse(str(UI_DIR / "pricing.html"))


@router.get("/impressum")
@router.get("/impressum/")
def impressum():
    return FileResponse(str(UI_DIR / "impressum.html"))


@router.get("/datenschutz")
@router.get("/datenschutz/")
def datenschutz():
    return FileResponse(str(UI_DIR / "datenschutz.html"))


@router.get("/jobcenters")
def jobcenters():
    if not os.path.exists(JOB_CENTER_JSON):
        return {"items": []}
    import json

    with open(JOB_CENTER_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = []
    if isinstance(data, list):
        for x in data:
            if not isinstance(x, dict):
                continue
            if not x.get("id") or not x.get("label"):
                continue
            items.append({
                "id": x["id"],
                "label": x["label"],
                "address": x.get("address") or "",
                "postalCode": x.get("postalCode") or "",
                "city": x.get("city") or "",
            })
    items.sort(key=lambda a: (a["label"] or "").lower())
    return {"items": items}
