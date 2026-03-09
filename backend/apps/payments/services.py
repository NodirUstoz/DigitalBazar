"""
Payment services: Stripe integration for payments, payouts, and refunds.
"""

import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.utils import timezone

from apps.orders.models import Order, LicenseKey
from .models import Payment, SellerPayout, RefundRequest

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripePaymentService:
    """Handles Stripe payment operations."""

    @staticmethod
    def create_payment_intent(order):
        """
        Create a Stripe PaymentIntent for the given order.
        Returns the client_secret for frontend confirmation.
        """
        try:
            amount_cents = int(order.total * 100)

            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="usd",
                metadata={
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "buyer_email": order.buyer.email,
                },
                automatic_payment_methods={"enabled": True},
            )

            # Create payment record
            payment = Payment.objects.create(
                order=order,
                buyer=order.buyer,
                amount=order.total,
                stripe_payment_intent_id=intent.id,
                status=Payment.Status.PENDING,
            )

            # Update order with payment intent ID
            order.stripe_payment_intent_id = intent.id
            order.status = Order.Status.PROCESSING
            order.save(update_fields=["stripe_payment_intent_id", "status"])

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount": str(order.total),
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {e}")
            raise

    @staticmethod
    def handle_payment_success(payment_intent_id):
        """
        Handle a successful payment.
        Called from the Stripe webhook handler.
        """
        try:
            payment = Payment.objects.select_related("order").get(
                stripe_payment_intent_id=payment_intent_id
            )
        except Payment.DoesNotExist:
            logger.error(
                f"Payment not found for intent: {payment_intent_id}"
            )
            return False

        # Update payment status
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        payment.status = Payment.Status.SUCCEEDED
        payment.stripe_charge_id = (
            intent.latest_charge if intent.latest_charge else ""
        )
        payment.save(update_fields=["status", "stripe_charge_id"])

        # Get receipt URL if charge exists
        if payment.stripe_charge_id:
            try:
                charge = stripe.Charge.retrieve(payment.stripe_charge_id)
                payment.stripe_receipt_url = charge.receipt_url or ""
                payment.save(update_fields=["stripe_receipt_url"])
            except Exception:
                pass

        # Complete the order
        order = payment.order
        order.status = Order.Status.COMPLETED
        order.stripe_charge_id = payment.stripe_charge_id
        order.completed_at = timezone.now()
        order.save(update_fields=["status", "stripe_charge_id", "completed_at"])

        # Trigger async order processing
        from apps.orders.tasks import process_order_completion
        process_order_completion.delay(str(order.id))

        logger.info(f"Payment succeeded for order {order.order_number}")
        return True

    @staticmethod
    def handle_payment_failure(payment_intent_id):
        """Handle a failed payment."""
        try:
            payment = Payment.objects.select_related("order").get(
                stripe_payment_intent_id=payment_intent_id
            )
        except Payment.DoesNotExist:
            logger.error(
                f"Payment not found for intent: {payment_intent_id}"
            )
            return False

        intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        payment.status = Payment.Status.FAILED
        payment.failure_reason = (
            intent.last_payment_error.message
            if intent.last_payment_error else "Unknown error"
        )
        payment.save(update_fields=["status", "failure_reason"])

        payment.order.status = Order.Status.FAILED
        payment.order.save(update_fields=["status"])

        logger.warning(f"Payment failed for order {payment.order.order_number}")
        return True

    @staticmethod
    def process_refund(refund_request):
        """
        Process an approved refund through Stripe.
        """
        try:
            payment = refund_request.order.payment
        except Payment.DoesNotExist:
            logger.error(
                f"No payment found for refund request {refund_request.id}"
            )
            return False

        try:
            refund_amount = refund_request.refund_amount or payment.amount
            amount_cents = int(refund_amount * 100)

            refund = stripe.Refund.create(
                payment_intent=payment.stripe_payment_intent_id,
                amount=amount_cents,
                reason="requested_by_customer",
                metadata={
                    "refund_request_id": str(refund_request.id),
                    "order_number": refund_request.order.order_number,
                },
            )

            refund_request.stripe_refund_id = refund.id
            refund_request.status = RefundRequest.Status.PROCESSED
            refund_request.resolved_at = timezone.now()
            refund_request.save(
                update_fields=["stripe_refund_id", "status", "resolved_at"]
            )

            # Update order status
            order = refund_request.order
            if refund_amount >= payment.amount:
                order.status = Order.Status.REFUNDED
                payment.status = Payment.Status.REFUNDED
                # Revoke all license keys
                for item in order.items.all():
                    try:
                        license_key = item.license_key
                        license_key.status = LicenseKey.Status.REVOKED
                        license_key.revoked_at = timezone.now()
                        license_key.save(
                            update_fields=["status", "revoked_at"]
                        )
                    except LicenseKey.DoesNotExist:
                        pass
                    item.is_refunded = True
                    item.save(update_fields=["is_refunded"])
            else:
                order.status = Order.Status.PARTIALLY_REFUNDED

            order.save(update_fields=["status"])
            payment.save(update_fields=["status"])

            logger.info(
                f"Refund processed for order {order.order_number}: ${refund_amount}"
            )
            return True

        except stripe.error.StripeError as e:
            logger.error(f"Stripe refund error: {e}")
            refund_request.status = RefundRequest.Status.PENDING
            refund_request.admin_notes += f"\nRefund failed: {str(e)}"
            refund_request.save(update_fields=["status", "admin_notes"])
            return False

    @staticmethod
    def create_seller_transfer(payout):
        """
        Transfer funds to a seller's connected Stripe account.
        """
        try:
            seller_profile = payout.seller.seller_profile
            if not seller_profile.stripe_account_id:
                logger.error(
                    f"No Stripe account for seller {payout.seller.email}"
                )
                payout.status = SellerPayout.Status.FAILED
                payout.failure_reason = "No connected Stripe account."
                payout.save(update_fields=["status", "failure_reason"])
                return False

            amount_cents = int(payout.amount * 100)

            transfer = stripe.Transfer.create(
                amount=amount_cents,
                currency=payout.currency,
                destination=seller_profile.stripe_account_id,
                metadata={
                    "payout_id": str(payout.id),
                    "seller_email": payout.seller.email,
                },
            )

            payout.stripe_transfer_id = transfer.id
            payout.status = SellerPayout.Status.COMPLETED
            payout.completed_at = timezone.now()
            payout.save(
                update_fields=["stripe_transfer_id", "status", "completed_at"]
            )

            logger.info(
                f"Transfer completed for seller {payout.seller.email}: "
                f"${payout.amount}"
            )
            return True

        except stripe.error.StripeError as e:
            logger.error(f"Stripe transfer error: {e}")
            payout.status = SellerPayout.Status.FAILED
            payout.failure_reason = str(e)
            payout.save(update_fields=["status", "failure_reason"])
            return False
