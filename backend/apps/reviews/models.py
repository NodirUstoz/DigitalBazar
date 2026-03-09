"""
Review models: Review, ReviewResponse.
Handles product ratings and reviews with moderation support.
"""

import uuid
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    """
    Product review submitted by a buyer after purchase.
    Requires a completed order for the reviewed product.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        "products.DigitalProduct",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    order_item = models.OneToOneField(
        "orders.OrderItem",
        on_delete=models.CASCADE,
        related_name="review",
        help_text="The specific order item this review is for.",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        db_index=True,
    )
    title = models.CharField(max_length=200)
    body = models.TextField(max_length=5000)
    is_approved = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Reviews require moderation before being public.",
    )
    is_featured = models.BooleanField(default=False)
    helpful_count = models.PositiveIntegerField(default=0)
    reported_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reviews"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["buyer", "product"],
                name="unique_review_per_product",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "-created_at"]),
            models.Index(fields=["product", "is_approved"]),
        ]

    def __str__(self):
        return f"{self.buyer.username} - {self.product.title} ({self.rating}/5)"


class ReviewResponse(models.Model):
    """
    Seller response to a buyer review.
    Each review may have at most one seller response.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.OneToOneField(
        Review,
        on_delete=models.CASCADE,
        related_name="response",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_responses",
    )
    body = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "review_responses"

    def __str__(self):
        return f"Response to review by {self.review.buyer.username}"


class ReviewHelpful(models.Model):
    """
    Tracks which users have marked a review as helpful.
    Prevents duplicate votes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="helpful_votes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="helpful_votes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "review_helpful"
        unique_together = ["review", "user"]

    def __str__(self):
        return f"{self.user.username} found review {self.review.id} helpful"
