"""
Analytics serializers.
"""

from rest_framework import serializers
from .models import ProductView, DownloadStat, SalesReport


class ProductViewSerializer(serializers.ModelSerializer):
    """Serializer for product view records."""

    product_title = serializers.CharField(
        source="product.title", read_only=True
    )

    class Meta:
        model = ProductView
        fields = (
            "id", "product_title", "ip_address", "referrer",
            "country", "viewed_at",
        )


class DownloadStatSerializer(serializers.ModelSerializer):
    """Serializer for download statistics."""

    product_title = serializers.CharField(
        source="product.title", read_only=True
    )

    class Meta:
        model = DownloadStat
        fields = (
            "id", "product_title", "date", "download_count",
            "unique_downloaders",
        )


class SalesReportSerializer(serializers.ModelSerializer):
    """Serializer for sales reports."""

    class Meta:
        model = SalesReport
        fields = (
            "id", "report_type", "report_date", "total_orders",
            "total_revenue", "total_platform_fees",
            "total_seller_earnings", "total_refunds",
            "new_customers", "top_products", "created_at",
        )


class DashboardSummarySerializer(serializers.Serializer):
    """Serializer for dashboard summary data."""

    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_sales = serializers.IntegerField()
    total_products = serializers.IntegerField()
    total_downloads = serializers.IntegerField()
    total_views = serializers.IntegerField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    recent_orders = serializers.ListField()
    revenue_chart = serializers.ListField()
