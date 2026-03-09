"""
Payment views: Stripe payment intents, webhooks, payouts, refunds.
"""

import logging
from datetime import timedelta

import stripe
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes as perm_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from .models import Payment, SellerPayout, RefundRequest
from .services import StripePaymentService

logger = logging.getLogger(__name__)


class CreatePaymentIntentView(APIView):
    """Create a Stripe PaymentIntent for an order."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        order_id = request.data.get("order_id")
        if not order_id:
            return Response(
                {"detail": "order_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = Order.objects.get(
                id=order_id,
                buyer=request.user,
                status__in=[Order.Status.PENDING, Order.Status.PROCESSING],
            )
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found or already processed."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = StripePaymentService.create_payment_intent(order)
            return Response(result, status=status.HTTP_200_OK)
        except stripe.error.StripeError as e:
            return Response(
                {"detail": f"Payment error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


@csrf_exempt
@api_view(["POST"])
@perm_classes([permissions.AllowAny])
def stripe_webhook(request):
    """
    Handle Stripe webhook events.
    Verifies the webhook signature and processes payment events.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid Stripe webhook payload.")
        return Response(status=status.HTTP_400_BAD_REQUEST)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid Stripe webhook signature.")
        return Response(status=status.HTTP_400_BAD_REQUEST)

    event_type = event["type"]
    data_object = event["data"]["object"]

    logger.info(f"Stripe webhook received: {event_type}")

    if event_type == "payment_intent.succeeded":
        StripePaymentService.handle_payment_success(data_object["id"])

    elif event_type == "payment_intent.payment_failed":
        StripePaymentService.handle_payment_failure(data_object["id"])

    elif event_type == "charge.refunded":
        payment_intent_id = data_object.get("payment_intent")
        if payment_intent_id:
            logger.info(f"Charge refunded for payment intent: {payment_intent_id}")

    return Response({"status": "ok"}, status=status.HTTP_200_OK)


class RefundRequestView(APIView):
    """Create a refund request for an order."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        order_id = request.data.get("order_id")
        reason = request.data.get("reason", RefundRequest.Reason.OTHER)
        description = request.data.get("description", "")

        if not order_id:
            return Response(
                {"detail": "order_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not description:
            return Response(
                {"detail": "A description is required for refund requests."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = Order.objects.get(
                id=order_id,
                buyer=request.user,
                status=Order.Status.COMPLETED,
            )
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found or not eligible for refund."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check 30-day refund window
        refund_deadline = order.completed_at + timedelta(days=30)
        if timezone.now() > refund_deadline:
            return Response(
                {"detail": "Refund window (30 days) has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for existing pending refund requests
        existing = RefundRequest.objects.filter(
            order=order,
            status__in=[RefundRequest.Status.PENDING, RefundRequest.Status.APPROVED],
        ).exists()
        if existing:
            return Response(
                {"detail": "A refund request already exists for this order."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refund_request = RefundRequest.objects.create(
            order=order,
            buyer=request.user,
            reason=reason,
            description=description,
            refund_amount=order.total,
        )

        return Response(
            {
                "id": str(refund_request.id),
                "status": refund_request.status,
                "detail": "Refund request submitted. It will be reviewed within 48 hours.",
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request):
        """List refund requests for the current user."""
        refund_requests = RefundRequest.objects.filter(buyer=request.user)
        data = [
            {
                "id": str(rr.id),
                "order_number": rr.order.order_number,
                "reason": rr.reason,
                "status": rr.status,
                "refund_amount": str(rr.refund_amount) if rr.refund_amount else None,
                "created_at": rr.created_at.isoformat(),
                "resolved_at": rr.resolved_at.isoformat() if rr.resolved_at else None,
            }
            for rr in refund_requests
        ]
        return Response(data)


class SellerPayoutListView(APIView):
    """List payouts for the authenticated seller."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        if not request.user.is_seller:
            return Response(
                {"detail": "You are not a seller."},
                status=status.HTTP_403_FORBIDDEN,
            )

        payouts = SellerPayout.objects.filter(seller=request.user)
        data = [
            {
                "id": str(p.id),
                "amount": str(p.amount),
                "currency": p.currency,
                "status": p.status,
                "created_at": p.created_at.isoformat(),
                "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            }
            for p in payouts
        ]
        return Response(data)
