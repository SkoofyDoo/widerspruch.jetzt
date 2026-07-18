"""Feedback form endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.feedback.mail import send_feedback_email
from app.testers.tokens import derive_email_from_token

router = APIRouter(tags=["feedback"])


@router.post("/feedback")
async def save_feedback(request: Request):
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise HTTPException(422, "Invalid payload")

        token = (data.get("token") or "").strip()
        derived = derive_email_from_token(token)
        if derived:
            data["email"] = derived

        send_feedback_email(data)
        return {"ok": True, "message": "Vielen Dank für dein Feedback!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
