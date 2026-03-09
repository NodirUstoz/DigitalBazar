"""
Product views: catalog listing, detail, CRUD, categories, file uploads.
"""

import hashlib

from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, permissions, status, parsers
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.pagination import StandardResultsSetPagination
from .models import (
    Category, Tag, DigitalProduct, License,
    ProductFile, ProductPreview,
)
from .serializers import (
    CategorySerializer, TagSerializer,
    ProductListSerializer, ProductDetailSerializer,
    ProductCreateSerializer, ProductFileUploadSerializer,
    ProductPreviewSerializer, LicenseSerializer,
)
from .filters import ProductFilter


class IsSellerOrReadOnly(permissions.BasePermission):
    """Allow sellers to create/edit, everyone can read."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.is_seller

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.seller == request.user


class CategoryListView(generics.ListAPIView):
    """List all active categories (with nested children)."""

    serializer_class = CategorySerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None

    def get_queryset(self):
        return Category.objects.filter(is_active=True, parent__isnull=True)


class CategoryDetailView(generics.RetrieveAPIView):
    """Get category details by slug."""

    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = "slug"


class TagListView(generics.ListAPIView):
    """List all tags."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None


class ProductListView(generics.ListAPIView):
    """
    List published products with filtering, search, and ordering.
    Supports filters: category, type, price range, rating, seller, tag.
    """

    serializer_class = ProductListSerializer
    permission_classes = (permissions.AllowAny,)
    filterset_class = ProductFilter
    search_fields = ["title", "description", "short_description", "tags__name"]
    ordering_fields = [
        "created_at", "sales_count", "average_rating", "view_count",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            DigitalProduct.objects
            .filter(status=DigitalProduct.Status.PUBLISHED)
            .select_related("category", "seller")
            .prefetch_related("tags", "licenses")
            .distinct()
        )


class ProductDetailView(generics.RetrieveAPIView):
    """
    Get product details by slug. Increments view count.
    """

    serializer_class = ProductDetailSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = "slug"

    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_seller:
            return (
                DigitalProduct.objects
                .filter(
                    Q(status=DigitalProduct.Status.PUBLISHED)
                    | Q(seller=self.request.user)
                )
                .select_related("category", "seller")
                .prefetch_related("tags", "licenses", "previews", "files")
            )
        return (
            DigitalProduct.objects
            .filter(status=DigitalProduct.Status.PUBLISHED)
            .select_related("category", "seller")
            .prefetch_related("tags", "licenses", "previews")
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Increment view count (fire-and-forget, no need for F expression
        # on every page view -- we batch-update via Celery)
        DigitalProduct.objects.filter(pk=instance.pk).update(
            view_count=instance.view_count + 1
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ProductCreateView(generics.CreateAPIView):
    """Create a new product (seller only)."""

    serializer_class = ProductCreateSerializer
    permission_classes = (permissions.IsAuthenticated, IsSellerOrReadOnly)

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)


class ProductUpdateView(generics.UpdateAPIView):
    """Update an existing product (owner only)."""

    serializer_class = ProductCreateSerializer
    permission_classes = (permissions.IsAuthenticated, IsSellerOrReadOnly)
    lookup_field = "slug"

    def get_queryset(self):
        return DigitalProduct.objects.filter(seller=self.request.user)


class ProductDeleteView(generics.DestroyAPIView):
    """Delete a product (owner only). Soft-deletes by archiving."""

    permission_classes = (permissions.IsAuthenticated, IsSellerOrReadOnly)
    lookup_field = "slug"

    def get_queryset(self):
        return DigitalProduct.objects.filter(seller=self.request.user)

    def perform_destroy(self, instance):
        instance.status = DigitalProduct.Status.ARCHIVED
        instance.save(update_fields=["status"])


class ProductPublishView(APIView):
    """Submit a product for review / publish."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, slug):
        try:
            product = DigitalProduct.objects.get(
                slug=slug, seller=request.user
            )
        except DigitalProduct.DoesNotExist:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not product.licenses.filter(is_active=True).exists():
            return Response(
                {"detail": "Product must have at least one active license before publishing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not product.files.exists():
            return Response(
                {"detail": "Product must have at least one file before publishing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product.status = DigitalProduct.Status.PENDING
        product.save(update_fields=["status"])
        return Response(
            {"detail": "Product submitted for review."},
            status=status.HTTP_200_OK,
        )


class SellerProductListView(generics.ListAPIView):
    """List all products for the authenticated seller (all statuses)."""

    serializer_class = ProductListSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return (
            DigitalProduct.objects
            .filter(seller=self.request.user)
            .exclude(status=DigitalProduct.Status.ARCHIVED)
            .select_related("category")
            .prefetch_related("tags", "licenses")
        )


class ProductFileUploadView(APIView):
    """Upload files for a product (owner only)."""

    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    def post(self, request, slug):
        try:
            product = DigitalProduct.objects.get(
                slug=slug, seller=request.user
            )
        except DigitalProduct.DoesNotExist:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"detail": "No file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Calculate file hash
        hasher = hashlib.sha256()
        for chunk in uploaded_file.chunks():
            hasher.update(chunk)
        file_hash = hasher.hexdigest()

        is_main = request.data.get("is_main", "false").lower() == "true"
        version = request.data.get("version", product.version)

        # If marking as main, unset other main files
        if is_main:
            product.files.filter(is_main=True).update(is_main=False)

        product_file = ProductFile.objects.create(
            product=product,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            file_size=uploaded_file.size,
            file_hash=file_hash,
            version=version,
            is_main=is_main,
        )

        return Response(
            {
                "id": str(product_file.id),
                "filename": product_file.original_filename,
                "size": product_file.file_size_display,
                "hash": product_file.file_hash,
            },
            status=status.HTTP_201_CREATED,
        )


class ProductPreviewUploadView(APIView):
    """Upload preview media for a product (owner only)."""

    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    def post(self, request, slug):
        try:
            product = DigitalProduct.objects.get(
                slug=slug, seller=request.user
            )
        except DigitalProduct.DoesNotExist:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProductPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(product=product)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, slug):
        preview_id = request.data.get("preview_id")
        if not preview_id:
            return Response(
                {"detail": "preview_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            preview = ProductPreview.objects.get(
                id=preview_id, product__slug=slug, product__seller=request.user
            )
        except ProductPreview.DoesNotExist:
            return Response(
                {"detail": "Preview not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        preview.file.delete()
        preview.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FeaturedProductsView(generics.ListAPIView):
    """List featured products."""

    serializer_class = ProductListSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None

    def get_queryset(self):
        return (
            DigitalProduct.objects
            .filter(
                status=DigitalProduct.Status.PUBLISHED,
                is_featured=True,
            )
            .select_related("category")
            .prefetch_related("tags", "licenses")[:12]
        )
