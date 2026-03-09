"""
Payment models: Payment, SellerPayout, RefundRequest.
"""

import uuid
from django.conf import settings
from django.db import models


class Payment(models.Model):
    """
    Tracks payment transactions processed through Stripe.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"
        REFUNDED = "refunded", "Refunded"

    class PaymentMethod(models.TextChoices):
        CARD = "card", "Credit/Debit Card"
        WALLET = "wallet", "Digital Wallet"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payment",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CARD,
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255, unique=True, db_index=True
    )
    stripe_charge_id = models.CharField(max_length=255, blank=True)
    stripe_receipt_url = models.URLField(blank=True)
    failure_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.id} - {self.order.order_number} ({self.status})"


class SellerPayout(models.Model):
    """
    Tracks payouts to sellers for their completed sales.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payouts",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    stripe_transfer_id = models.CharField(max_length=255, blank=True)
    stripe_payout_id = models.CharField(max_length=255, blank=True)
    failure_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "seller_payouts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payout {self.id} to {self.seller.email} - ${self.amount}"


class RefundRequest(models.Model):
    """
    Buyer-initiated refund request for an order.
    Requires admin approval before processing.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PROCESSED = "processed", "Processed"

    class Reason(models.TextChoices):
        NOT_AS_DESCRIBED = "not_as_described", "Not as described"
        DEFECTIVE = "defective", "Defective / Not working"
        DUPLICATE = "duplicate", "Duplicate purchase"
        ACCIDENTAL = "accidental", "Accidental purchase"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="refund_requests",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="refund_requests",
    )
    reason = models.CharField(
        max_length=30,
        choices=Reason.choices,
        default=Reason.OTHER,
    )
    description = models.TextField(
        max_length=2000,
        help_text="Detailed explanation for the refund request.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    refund_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    stripe_refund_id = models.CharField(max_length=255, blank=True)
    admin_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_refunds",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "refund_requests"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Refund {self.id} - Order {self.order.order_number} ({self.status})"
        )
