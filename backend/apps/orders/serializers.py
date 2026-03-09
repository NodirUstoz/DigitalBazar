"""
Order serializers.
"""

from rest_framework import serializers
from apps.products.serializers import ProductListSerializer
from .models import Order, OrderItem, LicenseKey, Download


class LicenseKeySerializer(serializers.ModelSerializer):
    """Serializer for license keys."""

    is_valid = serializers.ReadOnlyField()
    downloads_remaining = serializers.ReadOnlyField()
    product_title = serializers.CharField(
        source="order_item.product_title", read_only=True
    )

    class Meta:
        model = LicenseKey
        fields = (
            "id", "key", "status", "max_downloads", "download_count",
            "downloads_remaining", "is_valid", "product_title",
            "activated_at", "expires_at",
        )


class DownloadSerializer(serializers.ModelSerializer):
    """Serializer for download records."""

    filename = serializers.CharField(
        source="product_file.original_filename", read_only=True
    )

    class Meta:
        model = Download
        fields = ("id", "filename", "ip_address", "downloaded_at")


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order line items."""

    license_key = LicenseKeySerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id", "product_title", "license_name", "price",
            "seller_amount", "platform_fee", "is_refunded",
            "license_key", "created_at",
        )


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for order details."""

    items = OrderItemSerializer(many=True, read_only=True)
    item_count = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = (
            "id", "order_number", "status", "subtotal",
            "platform_fee", "total", "item_count", "items",
            "created_at", "completed_at",
        )


class OrderListSerializer(serializers.ModelSerializer):
    """Compact serializer for order listings."""

    item_count = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = (
            "id", "order_number", "status", "total",
            "item_count", "created_at",
        )


class CheckoutItemSerializer(serializers.Serializer):
    """Serializer for items in a checkout request."""

    product_id = serializers.UUIDField()
    license_id = serializers.UUIDField()


class CheckoutSerializer(serializers.Serializer):
    """Serializer for checkout requests."""

    items = CheckoutItemSerializer(many=True)
    affiliate_code = serializers.CharField(required=False, allow_blank=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        if len(value) > 20:
            raise serializers.ValidationError("Maximum 20 items per order.")
        return value
