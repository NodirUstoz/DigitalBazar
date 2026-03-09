"""
Review views: listing, creating, responding, and voting on reviews.
"""

from django.db.models import Avg, Count
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.models import DigitalProduct
from .models import Review, ReviewResponse
from .serializers import (
    ReviewListSerializer,
    ReviewDetailSerializer,
    ReviewCreateSerializer,
    ReviewResponseCreateSerializer,
    ReviewHelpfulSerializer,
)


class IsReviewOwnerOrReadOnly(permissions.BasePermission):
    """Allow review owners to edit, everyone can read."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.buyer == request.user


class ProductReviewListView(generics.ListAPIView):
    """
    List all approved reviews for a product.
    Supports ordering by rating, date, and helpfulness.
    """

    serializer_class = ReviewListSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        product_slug = self.kwargs["product_slug"]
        ordering = self.request.query_params.get("ordering", "-created_at")

        allowed_orderings = {
            "-created_at", "created_at",
            "-rating", "rating",
            "-helpful_count", "helpful_count",
        }
        if ordering not in allowed_orderings:
            ordering = "-created_at"

        return (
            Review.objects
            .filter(
                product__slug=product_slug,
                is_approved=True,
            )
            .select_related("buyer", "response", "response__seller")
            .order_by(ordering)
        )


class ProductReviewSummaryView(APIView):
    """
    Get review summary statistics for a product:
    average rating, total count, and distribution by star level.
    """

    permission_classes = (permissions.AllowAny,)

    def get(self, request, product_slug):
        try:
            product = DigitalProduct.objects.get(slug=product_slug)
        except DigitalProduct.DoesNotExist:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        reviews = Review.objects.filter(
            product=product, is_approved=True
        )

        aggregates = reviews.aggregate(
            average=Avg("rating"),
            total=Count("id"),
        )

        # Star distribution
        distribution = {}
        for star in range(1, 6):
            count = reviews.filter(rating=star).count()
            distribution[str(star)] = count

        return Response({
            "product_id": str(product.id),
            "product_slug": product.slug,
            "average_rating": round(aggregates["average"] or 0, 2),
            "total_reviews": aggregates["total"] or 0,
            "distribution": distribution,
        })


class ReviewCreateView(generics.CreateAPIView):
    """
    Create a new review for a purchased product.
    Requires authentication and a completed order.
    """

    serializer_class = ReviewCreateSerializer
    permission_classes = (permissions.IsAuthenticated,)


class ReviewUpdateView(generics.UpdateAPIView):
    """Update an existing review (owner only)."""

    serializer_class = ReviewCreateSerializer
    permission_classes = (permissions.IsAuthenticated, IsReviewOwnerOrReadOnly)
    lookup_field = "id"

    def get_queryset(self):
        return Review.objects.filter(buyer=self.request.user)


class ReviewDeleteView(generics.DestroyAPIView):
    """Delete a review (owner only)."""

    permission_classes = (permissions.IsAuthenticated, IsReviewOwnerOrReadOnly)
    lookup_field = "id"

    def get_queryset(self):
        return Review.objects.filter(buyer=self.request.user)


class ReviewResponseView(APIView):
    """
    Seller responds to a review on their product.
    Only one response per review is allowed.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, review_id):
        try:
            review = Review.objects.select_related("product").get(id=review_id)
        except Review.DoesNotExist:
            return Response(
                {"detail": "Review not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ReviewResponseCreateSerializer(
            data=request.data,
            context={"request": request, "review": review},
        )
        serializer.is_valid(raise_exception=True)
        response_obj = serializer.save()

        return Response(
            ReviewResponseCreateSerializer(response_obj).data,
            status=status.HTTP_201_CREATED,
        )


class ReviewHelpfulView(APIView):
    """Mark a review as helpful. Toggle on/off."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, review_id):
        try:
            review = Review.objects.get(id=review_id, is_approved=True)
        except Review.DoesNotExist:
            return Response(
                {"detail": "Review not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if review.buyer == request.user:
            return Response(
                {"detail": "You cannot vote on your own review."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ReviewHelpfulSerializer(
            data={},
            context={"request": request, "review": review},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response({
            "helpful_count": result["helpful_count"],
            "voted": result["created"],
        })


class SellerReviewListView(generics.ListAPIView):
    """List all reviews across the seller's products."""

    serializer_class = ReviewDetailSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return (
            Review.objects
            .filter(product__seller=self.request.user)
            .select_related("buyer", "product", "response")
            .order_by("-created_at")
        )
