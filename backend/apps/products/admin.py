"""
Product admin configuration.
"""

from django.contrib import admin
from .models import (
    Category, Tag, DigitalProduct, License,
    ProductFile, ProductPreview,
)


class LicenseInline(admin.TabularInline):
    model = License
    extra = 1


class ProductFileInline(admin.TabularInline):
    model = ProductFile
    extra = 0
    readonly_fields = ("file_hash", "file_size", "uploaded_at")


class ProductPreviewInline(admin.TabularInline):
    model = ProductPreview
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("sort_order", "name")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(DigitalProduct)
class DigitalProductAdmin(admin.ModelAdmin):
    list_display = (
        "title", "seller", "product_type", "status",
        "is_featured", "sales_count", "average_rating", "created_at",
    )
    list_filter = ("status", "product_type", "is_featured", "category")
    search_fields = ("title", "description", "seller__email")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = (
        "view_count", "download_count", "sales_count",
        "average_rating", "review_count",
        "created_at", "updated_at", "published_at",
    )
    inlines = [LicenseInline, ProductFileInline, ProductPreviewInline]

    actions = ["publish_products", "reject_products", "feature_products"]

    @admin.action(description="Publish selected products")
    def publish_products(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(
            status=DigitalProduct.Status.PENDING
        ).update(
            status=DigitalProduct.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.message_user(request, f"{updated} product(s) published.")

    @admin.action(description="Reject selected products")
    def reject_products(self, request, queryset):
        updated = queryset.filter(
            status=DigitalProduct.Status.PENDING
        ).update(status=DigitalProduct.Status.REJECTED)
        self.message_user(request, f"{updated} product(s) rejected.")

    @admin.action(description="Toggle featured status")
    def feature_products(self, request, queryset):
        for product in queryset:
            product.is_featured = not product.is_featured
            product.save(update_fields=["is_featured"])
        self.message_user(request, "Featured status toggled.")


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = (
        "product", "license_type", "name", "price",
        "max_downloads", "is_active",
    )
    list_filter = ("license_type", "is_active")
    search_fields = ("product__title", "name")
