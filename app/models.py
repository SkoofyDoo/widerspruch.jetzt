"""Pydantic request/response models for the public API."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel

from app.config import DEFAULT_K

Style = Literal["standard", "formal", "short"]
OutFormat = Literal["txt", "pdf", "json"]


class SearchHit(BaseModel):
    id: str
    score: float
    text: str
    source_file: str
    law: str = ""
    paragraph: str = ""


class WiderspruchWorkflowRequest(BaseModel):
    user_id: Optional[str] = None
    text: Optional[str] = None
    question: Optional[str] = None
    facts: Optional[Dict[str, Any]] = None
    k: int = DEFAULT_K
    format: OutFormat = "txt"
    filename: Optional[str] = None
    language: str = "de"
    style: Style = "standard"
    include_quellen: bool = False
    include_context: bool = False
    preview: bool = False
    letter_text: Optional[str] = None


class CheckoutRequest(BaseModel):
    user_id: str
    days: int = 7
