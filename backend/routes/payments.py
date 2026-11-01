"""Stripe payment processing and subscription billing."""

import stripe
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel

from database import get_db
from models import (
    User, Consultation, ProfessionalSubscription,
    SubscriptionStatus, ConsultationStatus, JobSubscription
)
from .auth import get_current_user

router = APIRouter()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_test")


class PaymentIntentResponse(BaseModel):
    client_secret: str
    amount: int
    currency: str


class SubscriptionCreateResponse(BaseModel):
    subscription_id: str
    status: str
    current_period_end: datetime
    amount: float


class ProfessionalEarningsResponse(BaseModel):
    total_earnings: float
    total_commissions_paid: float
    current_balance: float
    subscription_status: str


@router.post("/consultation/{consultation_id}/pay", response_model=PaymentIntentResponse)
async def create_payment_intent(
    consultation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Stripe payment intent for a consultation."""
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    # Verify current user is the client
    if consultation.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Can't pay for cancelled consultations
    if consultation.status == ConsultationStatus.CANCELLED.value:
        raise HTTPException(status_code=400, detail="Cannot pay for cancelled consultation")

    try:
        # Create payment intent (amount in cents)
        intent = stripe.PaymentIntent.create(
            amount=int(consultation.total_price * 100),
            currency="usd",
            metadata={
                "consultation_id": consultation_id,
                "client_id": consultation.client_id,
                "professional_id": consultation.professional_id
            }
        )

        return PaymentIntentResponse(
            client_secret=intent.client_secret,
            amount=intent.amount,
            currency=intent.currency
        )

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def handle_stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook for payment confirmations."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle payment_intent.succeeded
    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]

        consultation_id = intent["metadata"].get("consultation_id")
        if consultation_id:
            consultation = db.query(Consultation).filter(
                Consultation.id == consultation_id
            ).first()

            if consultation:
                # Mark consultation as confirmed (payment received)
                consultation.status = ConsultationStatus.CONFIRMED.value

                # Add earnings to professional's subscription
                professional = db.query(User).filter(
                    User.id == consultation.professional_id
                ).first()

                if professional and professional.professional_profile:
                    subscription = professional.professional_profile.subscription
                    if subscription:
                        subscription.total_earnings += consultation.total_price
                        subscription.current_balance += consultation.professional_receives

                db.commit()

    # Handle payment_intent.payment_failed
    elif event["type"] == "payment_intent.payment_failed":
        # Log failure, optionally notify user
        pass

    # Handle customer.subscription.updated
    elif event["type"] == "customer.subscription.updated":
        stripe_subscription_id = event["data"]["object"]["id"]
        subscription = db.query(ProfessionalSubscription).filter(
            ProfessionalSubscription.stripe_subscription_id == stripe_subscription_id
        ).first()

        if subscription:
            # Update subscription status
            stripe_status = event["data"]["object"]["status"]
            if stripe_status == "active":
                subscription.status = SubscriptionStatus.ACTIVE.value
            elif stripe_status == "past_due":
                subscription.status = SubscriptionStatus.PAUSED.value
            elif stripe_status == "canceled":
                subscription.status = SubscriptionStatus.CANCELLED.value

            db.commit()

    return {"status": "received"}


@router.post("/subscription/create", response_model=SubscriptionCreateResponse)
async def create_professional_subscription(
    plan_type: str = "basic",  # "basic", "pro", "premium"
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a professional subscription."""
    if not current_user.professional_profile:
        raise HTTPException(status_code=403, detail="Not a professional")

    # Check if already has active subscription
    existing = db.query(ProfessionalSubscription).filter(
        ProfessionalSubscription.professional_id == current_user.professional_profile.id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already has subscription")

    # Plan pricing
    plan_prices = {
        "basic": 3500,  # $35/month in cents
        "pro": 6500,    # $65/month
        "premium": 8500  # $85/month
    }

    price_cents = plan_prices.get(plan_type, 4900)

    try:
        # Create Stripe customer
        customer = stripe.Customer.create(
            email=current_user.email,
            name=f"{current_user.first_name} {current_user.last_name}",
            metadata={"professional_id": current_user.professional_profile.id}
        )

        # Create recurring subscription
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price_data": {
                "unit_amount": price_cents,
                "currency": "usd",
                "recurring": {"interval": "month"}
            }}],
            metadata={"professional_id": current_user.professional_profile.id}
        )

        # Save to database
        billing_start = datetime.utcnow()
        billing_end = billing_start + timedelta(days=30)

        prof_subscription = ProfessionalSubscription(
            professional_id=current_user.professional_profile.id,
            plan_type=plan_type,
            monthly_price=price_cents / 100,
            status=SubscriptionStatus.ACTIVE.value,
            stripe_subscription_id=subscription.id,
            billing_period_start=billing_start,
            billing_period_end=billing_end
        )

        db.add(prof_subscription)
        db.commit()
        db.refresh(prof_subscription)

        return SubscriptionCreateResponse(
            subscription_id=subscription.id,
            status=subscription.status,
            current_period_end=datetime.fromtimestamp(
                subscription.current_period_end
            ),
            amount=price_cents / 100
        )

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscription", response_model=SubscriptionCreateResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current subscription details."""
    if not current_user.professional_profile:
        raise HTTPException(status_code=403, detail="Not a professional")

    subscription = db.query(ProfessionalSubscription).filter(
        ProfessionalSubscription.professional_id == current_user.professional_profile.id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription")

    try:
        # Get latest from Stripe
        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)

        return SubscriptionCreateResponse(
            subscription_id=subscription.stripe_subscription_id,
            status=stripe_sub.status,
            current_period_end=datetime.fromtimestamp(
                stripe_sub.current_period_end
            ),
            amount=subscription.monthly_price
        )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/subscription/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel professional subscription."""
    if not current_user.professional_profile:
        raise HTTPException(status_code=403, detail="Not a professional")

    subscription = db.query(ProfessionalSubscription).filter(
        ProfessionalSubscription.professional_id == current_user.professional_profile.id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")

    try:
        stripe.Subscription.delete(subscription.stripe_subscription_id)

        subscription.status = SubscriptionStatus.CANCELLED.value
        db.commit()

        return {"message": "Subscription cancelled"}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/earnings", response_model=ProfessionalEarningsResponse)
async def get_professional_earnings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get professional earnings and commission information."""
    if not current_user.professional_profile:
        raise HTTPException(status_code=403, detail="Not a professional")

    subscription = db.query(ProfessionalSubscription).filter(
        ProfessionalSubscription.professional_id == current_user.professional_profile.id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription")

    return ProfessionalEarningsResponse(
        total_earnings=subscription.total_earnings,
        total_commissions_paid=subscription.total_commissions_paid,
        current_balance=subscription.current_balance,
        subscription_status=subscription.status
    )


@router.post("/job-subscription/create", response_model=dict)
async def create_job_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a job posting subscription ($50/year annual plan)."""

    # Check if already has active subscription
    existing = db.query(JobSubscription).filter(
        JobSubscription.user_id == current_user.id,
        JobSubscription.status == "active"
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already has active job subscription")

    try:
        # Create Stripe customer if doesn't exist
        customer = stripe.Customer.create(
            email=current_user.email,
            name=f"{current_user.first_name} {current_user.last_name}",
            metadata={"user_id": current_user.id, "type": "job_subscription"}
        )

        # Create annual subscription at $50/year (5000 cents)
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price_data": {
                "unit_amount": 5000,  # $50/year
                "currency": "usd",
                "recurring": {"interval": "year"}
            }}],
            metadata={"user_id": current_user.id}
        )

        # Save to database
        subscription_start = datetime.utcnow()
        subscription_end = subscription_start + timedelta(days=365)

        job_sub = JobSubscription(
            user_id=current_user.id,
            status="active",
            subscription_start=subscription_start,
            subscription_end=subscription_end,
            renewal_date=subscription_end,
            stripe_subscription_id=subscription.id
        )

        db.add(job_sub)
        db.commit()
        db.refresh(job_sub)

        return {
            "subscription_id": subscription.id,
            "status": "active",
            "price": "$50/year",
            "expires": subscription_end.isoformat(),
            "max_concurrent_jobs": 10,
            "message": "Job posting subscription activated"
        }

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payout")
async def request_payout(
    amount: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Request a payout of earnings."""
    if not current_user.professional_profile:
        raise HTTPException(status_code=403, detail="Not a professional")

    subscription = db.query(ProfessionalSubscription).filter(
        ProfessionalSubscription.professional_id == current_user.professional_profile.id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription")

    if amount > subscription.current_balance:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    try:
        # Create payout to connected account (in production, use Stripe Connect)
        payout = stripe.Payout.create(
            amount=int(amount * 100),
            currency="usd",
            metadata={"professional_id": current_user.professional_profile.id}
        )

        # Update balance
        subscription.current_balance -= amount
        subscription.total_commissions_paid += amount
        db.commit()

        return {
            "payout_id": payout.id,
            "amount": amount,
            "status": payout.status,
            "new_balance": subscription.current_balance
        }

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
