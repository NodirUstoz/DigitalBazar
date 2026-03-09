"""
Product URL routing.
"""

from django.urls import path
from . import views

app_name = "products"

urlpatterns = [
    # Categories
    path("categories/", views.CategoryListView.as_view(), name="category-list"),
    path(
        "categories/<slug:slug>/",
        views.CategoryDetailView.as_view(),
        name="category-detail",
    ),

    # Tags
    path("tags/", views.TagListView.as_view(), name="tag-list"),

    # Product listing and detail
    path("", views.ProductListView.as_view(), name="product-list"),
    path("featured/", views.FeaturedProductsView.as_view(), name="featured-products"),
    path("<slug:slug>/", views.ProductDetailView.as_view(), name="product-detail"),

    # Product CRUD (seller)
    path("create/", views.ProductCreateView.as_view(), name="product-create"),
    path("<slug:slug>/update/", views.ProductUpdateView.as_view(), name="product-update"),
    path("<slug:slug>/delete/", views.ProductDeleteView.as_view(), name="product-delete"),
    path("<slug:slug>/publish/", views.ProductPublishView.as_view(), name="product-publish"),

    # Seller product management
    path("my/products/", views.SellerProductListView.as_view(), name="seller-products"),

    # File and preview uploads
    path(
        "<slug:slug>/files/",
        views.ProductFileUploadView.as_view(),
        name="product-file-upload",
    ),
    path(
        "<slug:slug>/previews/",
        views.ProductPreviewUploadView.as_view(),
        name="product-preview-upload",
    ),
]
