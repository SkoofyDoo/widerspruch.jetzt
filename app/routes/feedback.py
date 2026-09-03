"""Feedback form endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.feedback.mail import send_feedback_email

router = APIRouter(tags=["feedback"])


@router.post("/feedback")
async def save_feedback(request: Request):
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise HTTPException(422, "Invalid payload")

        send_feedback_email(data)
        return {"ok": True, "message": "Vielen Dank für dein Feedback!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
