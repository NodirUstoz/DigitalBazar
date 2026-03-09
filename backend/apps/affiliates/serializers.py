"""
Affiliate serializers.
"""

from rest_framework import serializers
from .models import AffiliateProgram, AffiliateLink, Commission


class AffiliateProgramSerializer(serializers.ModelSerializer):
    """Serializer for affiliate programs."""

    product_title = serializers.CharField(
        source="product.title", read_only=True
    )
    product_slug = serializers.CharField(
        source="product.slug", read_only=True
    )
    seller_name = serializers.CharField(
        source="seller.username", read_only=True
    )

    class Meta:
        model = AffiliateProgram
        fields = (
            "id", "product_title", "product_slug", "seller_name",
            "commission_rate", "cookie_duration_days", "minimum_payout",
            "is_active", "terms", "total_affiliates", "total_referrals",
            "created_at",
        )
        read_only_fields = (
            "id", "total_affiliates", "total_referrals",
            "total_commissions_paid", "created_at",
        )


class AffiliateProgramCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating affiliate programs."""

    class Meta:
        model = AffiliateProgram
        fields = (
            "product", "commission_rate", "cookie_duration_days",
            "minimum_payout", "is_active", "terms",
        )

    def validate_commission_rate(self, value):
        if value < 1 or value > 50:
            raise serializers.ValidationError(
                "Commission rate must be between 1% and 50%."
            )
        return value


class AffiliateLinkSerializer(serializers.ModelSerializer):
    """Serializer for affiliate links."""

    referral_url = serializers.ReadOnlyField()
    conversion_rate = serializers.ReadOnlyField()
    product_title = serializers.CharField(
        source="program.product.title", read_only=True
    )

    class Meta:
        model = AffiliateLink
        fields = (
            "id", "product_title", "code", "referral_url",
            "is_active", "click_count", "conversion_count",
            "conversion_rate", "total_earned", "created_at",
        )
        read_only_fields = (
            "id", "code", "click_count", "conversion_count",
            "total_earned", "created_at",
        )


class CommissionSerializer(serializers.ModelSerializer):
    """Serializer for commission records."""

    product_title = serializers.CharField(
        source="affiliate_link.program.product.title", read_only=True
    )
    order_number = serializers.CharField(
        source="order.order_number", read_only=True
    )

    class Meta:
        model = Commission
        fields = (
            "id", "product_title", "order_number", "amount",
            "status", "paid_at", "created_at",
        )
