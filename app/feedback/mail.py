"""Send product feedback via SMTP."""

from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage

from app.config import FEEDBACK_TO, SMTP_FROM, SMTP_HOST, SMTP_KEY, SMTP_PORT, SMTP_USER
from app.testers.tokens import derive_email_from_token


def send_feedback_email(data: dict) -> None:
    if not SMTP_HOST or not SMTP_USER or not SMTP_KEY:
        raise RuntimeError("SMTP env not configured")

    token = (data.get("token") or "").strip()
    derived = derive_email_from_token(token)
    user_email = derived or ((data.get("email") or "").strip().lower())
    if not user_email:
        user_email = "unknown"

    rating = data.get("rating")
    quality = data.get("quality")

    msg = EmailMessage()
    msg["Subject"] = f"[Feedback] {rating}★ | {quality} | {user_email}"
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = FEEDBACK_TO
    if user_email != "unknown":
        msg["Reply-To"] = user_email
    msg.set_content(json.dumps(data, ensure_ascii=False, indent=2))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_KEY)
        s.send_message(msg)
