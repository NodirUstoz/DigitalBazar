"""
Analytics models: ProductView, DownloadStat, SalesReport.
"""

import uuid
from django.conf import settings
from django.db import models


class ProductView(models.Model):
    """
    Tracks individual product page views for analytics.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        "products.DigitalProduct",
        on_delete=models.CASCADE,
        related_name="analytics_views",
    )
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_views",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=2, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "product_views"
        ordering = ["-viewed_at"]
        indexes = [
            models.Index(fields=["product", "viewed_at"]),
        ]

    def __str__(self):
        return f"View: {self.product.title} at {self.viewed_at}"


class DownloadStat(models.Model):
    """
    Aggregated download statistics per product per day.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        "products.DigitalProduct",
        on_delete=models.CASCADE,
        related_name="download_stats",
    )
    date = models.DateField(db_index=True)
    download_count = models.PositiveIntegerField(default=0)
    unique_downloaders = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "download_stats"
        ordering = ["-date"]
        unique_together = ["product", "date"]

    def __str__(self):
        return f"{self.product.title}: {self.download_count} downloads on {self.date}"


class SalesReport(models.Model):
    """
    Aggregated sales report data. Generated daily/weekly/monthly by Celery tasks.
    """

    class ReportType(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sales_reports",
        help_text="Null for platform-wide reports.",
    )
    report_type = models.CharField(
        max_length=10,
        choices=ReportType.choices,
        default=ReportType.DAILY,
    )
    report_date = models.DateField(db_index=True)
    total_orders = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    total_platform_fees = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    total_seller_earnings = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    total_refunds = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    new_customers = models.PositiveIntegerField(default=0)
    top_products = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sales_reports"
        ordering = ["-report_date"]
        unique_together = ["seller", "report_type", "report_date"]

    def __str__(self):
        scope = self.seller.email if self.seller else "Platform"
        return f"{self.report_type} report for {scope} on {self.report_date}"
