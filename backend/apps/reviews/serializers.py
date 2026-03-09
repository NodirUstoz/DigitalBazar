"""
Review serializers for creating, listing, and responding to product reviews.
"""

from django.db.models import F
from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.orders.models import OrderItem, Order
from .models import Review, ReviewResponse, ReviewHelpful


class ReviewResponseSerializer(serializers.ModelSerializer):
    """Serializer for seller responses to reviews."""

    seller_name = serializers.CharField(source="seller.username", read_only=True)

    class Meta:
        model = ReviewResponse
        fields = ("id", "seller_name", "body", "created_at", "updated_at")
        read_only_fields = ("id", "seller_name", "created_at", "updated_at")


class ReviewListSerializer(serializers.ModelSerializer):
    """Compact serializer for review listings on product pages."""

    buyer_name = serializers.CharField(source="buyer.username", read_only=True)
    buyer_avatar = serializers.ImageField(source="buyer.avatar", read_only=True)
    response = ReviewResponseSerializer(read_only=True)
    has_voted_helpful = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = (
            "id", "rating", "title", "body",
            "buyer_name", "buyer_avatar",
            "is_featured", "helpful_count",
            "has_voted_helpful", "response",
            "created_at",
        )

    def get_has_voted_helpful(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return ReviewHelpful.objects.filter(
                review=obj, user=request.user
            ).exists()
        return False


class ReviewDetailSerializer(serializers.ModelSerializer):
    """Full review detail including buyer info and response."""

    buyer = UserSerializer(read_only=True)
    response = ReviewResponseSerializer(read_only=True)

    class Meta:
        model = Review
        fields = (
            "id", "product", "buyer", "rating", "title", "body",
            "is_approved", "is_featured", "helpful_count",
            "response", "created_at", "updated_at",
        )


class ReviewCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new review."""

    order_item_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Review
        fields = ("order_item_id", "rating", "title", "body")

    def validate_order_item_id(self, value):
        """Validate that the user purchased this product and hasn't already reviewed it."""
        request = self.context["request"]

        try:
            order_item = OrderItem.objects.select_related(
                "order", "product"
            ).get(
                id=value,
                order__buyer=request.user,
                order__status=Order.Status.COMPLETED,
                is_refunded=False,
            )
        except OrderItem.DoesNotExist:
            raise serializers.ValidationError(
                "Order item not found or not eligible for review."
            )

        # Check for existing review
        if Review.objects.filter(
            buyer=request.user, product=order_item.product
        ).exists():
            raise serializers.ValidationError(
                "You have already reviewed this product."
            )

        return value

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def create(self, validated_data):
        request = self.context["request"]
        order_item_id = validated_data.pop("order_item_id")
        order_item = OrderItem.objects.select_related("product").get(id=order_item_id)

        review = Review.objects.create(
            product=order_item.product,
            buyer=request.user,
            order_item=order_item,
            **validated_data,
        )
        return review


class ReviewResponseCreateSerializer(serializers.ModelSerializer):
    """Serializer for sellers responding to reviews."""

    class Meta:
        model = ReviewResponse
        fields = ("body",)

    def validate(self, attrs):
        review = self.context["review"]
        request = self.context["request"]

        # Only the product seller can respond
        if review.product.seller != request.user:
            raise serializers.ValidationError(
                "Only the product seller can respond to reviews."
            )

        # Check for existing response
        if hasattr(review, "response"):
            raise serializers.ValidationError(
                "This review already has a response."
            )

        return attrs

    def create(self, validated_data):
        review = self.context["review"]
        request = self.context["request"]

        response = ReviewResponse.objects.create(
            review=review,
            seller=request.user,
            **validated_data,
        )
        return response


class ReviewHelpfulSerializer(serializers.Serializer):
    """Serializer for marking a review as helpful."""

    def create(self, validated_data):
        request = self.context["request"]
        review = self.context["review"]

        helpful, created = ReviewHelpful.objects.get_or_create(
            review=review,
            user=request.user,
        )

        if created:
            Review.objects.filter(pk=review.pk).update(
                helpful_count=F("helpful_count") + 1
            )

        return {"created": created, "helpful_count": review.helpful_count + (1 if created else 0)}
