"""Stripe checkout and webhook routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.billing.access import (
    create_checkout_session,
    dedup_event,
    find_user_by_charge,
    require_stripe_config,
    revoke_access,
    set_user_access,
    stripe_webhook_secret,
)
from app.deps import stripe
from app.models import CheckoutRequest

router = APIRouter(tags=["billing"])


@router.post("/billing/checkout")
def billing_checkout(req: CheckoutRequest):
    return create_checkout_session(user_id=req.user_id, days=req.days)


@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    require_stripe_config()
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature") or request.headers.get("stripe-signature") or ""
    whsec = stripe_webhook_secret()

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, whsec)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
    except Exception as e:
        raise HTTPException(400, f"Webhook parse error: {e}")

    event_id = event.get("id", "")
    event_type = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    try:
        if dedup_event(event_id):
            return {"ok": True, "dedup": True}
    except Exception as e:
        print("Dedup store error:", repr(e))

    try:
        if event_type == "checkout.session.completed":
            metadata = obj.get("metadata") or {}
            user_id = (metadata.get("user_id") or "").strip()
            days = max(1, min(int((metadata.get("days") or "7").strip() or "7"), 365))
            customer_id = obj.get("customer") or ""
            session_id = obj.get("id") or ""
            payment_intent_id = obj.get("payment_intent") or ""
            charge_id = ""
            if payment_intent_id:
                pi = stripe.PaymentIntent.retrieve(payment_intent_id)
                charge_id = pi.get("latest_charge") or ""
            if user_id:
                set_user_access(
                    user_id=user_id,
                    days=days,
                    stripe_customer_id=customer_id,
                    session_id=session_id,
                    charge_id=charge_id,
                    payment_intent_id=payment_intent_id,
                )
        elif event_type == "charge.refunded":
            charge_id = obj.get("id") or ""
            user_id = find_user_by_charge(charge_id)
            if user_id:
                revoke_access(user_id=user_id)
    except Exception as e:
        print("Webhook handler error:", repr(e), "event_type:", event_type)

    return {"ok": True}
