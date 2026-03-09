"""
Order models: Order, OrderItem, Download, LicenseKey.
"""

import uuid
from django.conf import settings
from django.db import models


class Order(models.Model):
    """
    Represents a purchase transaction containing one or more digital products.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(
        max_length=20, unique=True, db_index=True
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    stripe_charge_id = models.CharField(max_length=255, blank=True)

    affiliate_link = models.ForeignKey(
        "affiliates.AffiliateLink",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order {self.order_number} - {self.buyer.email}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            import shortuuid
            self.order_number = f"DB-{shortuuid.uuid()[:8].upper()}"
        super().save(*args, **kwargs)

    @property
    def item_count(self):
        return self.items.count()


class OrderItem(models.Model):
    """
    Individual line item within an order, representing one product + license purchase.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "products.DigitalProduct",
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
    )
    license = models.ForeignKey(
        "products.License",
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sold_items",
    )
    product_title = models.CharField(max_length=255)
    license_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    seller_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    platform_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    is_refunded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_items"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.product_title} - {self.license_name}"


class LicenseKey(models.Model):
    """
    Generated license key for a purchased product.
    Used for software activation and download authorization.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_item = models.OneToOneField(
        OrderItem, on_delete=models.CASCADE, related_name="license_key"
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="license_keys",
    )
    key = models.CharField(max_length=255, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    max_downloads = models.PositiveIntegerField(default=1)
    download_count = models.PositiveIntegerField(default=0)
    activated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "license_keys"
        ordering = ["-activated_at"]

    def __str__(self):
        return f"{self.key} ({self.status})"

    @property
    def is_valid(self):
        if self.status != self.Status.ACTIVE:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        if self.max_downloads > 0 and self.download_count >= self.max_downloads:
            return False
        return True

    @property
    def downloads_remaining(self):
        if self.max_downloads == 0:
            return -1  # unlimited
        return max(0, self.max_downloads - self.download_count)


class Download(models.Model):
    """
    Tracks individual file downloads by buyers.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    license_key = models.ForeignKey(
        LicenseKey, on_delete=models.CASCADE, related_name="downloads"
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="downloads",
    )
    product_file = models.ForeignKey(
        "products.ProductFile",
        on_delete=models.SET_NULL,
        null=True,
        related_name="downloads",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "downloads"
        ordering = ["-downloaded_at"]

    def __str__(self):
        return (
            f"Download by {self.buyer.email} - "
            f"{self.product_file.original_filename if self.product_file else 'N/A'}"
        )


# Import timezone for LicenseKey.is_valid property
from django.utils import timezone  # noqa: E402
