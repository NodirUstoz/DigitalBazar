"""
Review URL routing.
"""

from django.urls import path
from . import views

app_name = "reviews"

urlpatterns = [
    # Product reviews (public)
    path(
        "products/<slug:product_slug>/",
        views.ProductReviewListView.as_view(),
        name="product-reviews",
    ),
    path(
        "products/<slug:product_slug>/summary/",
        views.ProductReviewSummaryView.as_view(),
        name="product-review-summary",
    ),

    # Review CRUD
    path("create/", views.ReviewCreateView.as_view(), name="review-create"),
    path(
        "<uuid:id>/update/",
        views.ReviewUpdateView.as_view(),
        name="review-update",
    ),
    path(
        "<uuid:id>/delete/",
        views.ReviewDeleteView.as_view(),
        name="review-delete",
    ),

    # Review interactions
    path(
        "<uuid:review_id>/respond/",
        views.ReviewResponseView.as_view(),
        name="review-respond",
    ),
    path(
        "<uuid:review_id>/helpful/",
        views.ReviewHelpfulView.as_view(),
        name="review-helpful",
    ),

    # Seller review management
    path(
        "seller/",
        views.SellerReviewListView.as_view(),
        name="seller-reviews",
    ),
]
