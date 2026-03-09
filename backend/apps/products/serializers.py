"""
Product serializers for catalog, categories, licenses, and files.
"""

from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from .models import (
    Category, Tag, DigitalProduct, License,
    ProductFile, ProductPreview,
)


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for product categories."""

    product_count = serializers.ReadOnlyField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            "id", "name", "slug", "description", "icon",
            "parent", "product_count", "children", "is_active",
        )

    def get_children(self, obj):
        children = obj.children.filter(is_active=True)
        return CategorySerializer(children, many=True).data


class TagSerializer(serializers.ModelSerializer):
    """Serializer for product tags."""

    class Meta:
        model = Tag
        fields = ("id", "name", "slug")


class LicenseSerializer(serializers.ModelSerializer):
    """Serializer for product license tiers."""

    class Meta:
        model = License
        fields = (
            "id", "license_type", "name", "price", "description",
            "features", "max_downloads", "is_active", "sort_order",
        )


class ProductFileSerializer(serializers.ModelSerializer):
    """Serializer for product files (admin/seller view)."""

    file_size_display = serializers.ReadOnlyField()

    class Meta:
        model = ProductFile
        fields = (
            "id", "original_filename", "file_size", "file_size_display",
            "file_hash", "version", "is_main", "uploaded_at",
        )


class ProductFileUploadSerializer(serializers.ModelSerializer):
    """Serializer for uploading product files."""

    class Meta:
        model = ProductFile
        fields = ("file", "original_filename", "version", "is_main")


class ProductPreviewSerializer(serializers.ModelSerializer):
    """Serializer for product preview media."""

    class Meta:
        model = ProductPreview
        fields = (
            "id", "preview_type", "file", "title",
            "alt_text", "sort_order",
        )


class ProductListSerializer(serializers.ModelSerializer):
    """Compact product serializer for list views."""

    category = CategorySerializer(read_only=True)
    seller_name = serializers.ReadOnlyField()
    base_price = serializers.ReadOnlyField()
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = DigitalProduct
        fields = (
            "id", "title", "slug", "short_description", "product_type",
            "category", "tags", "thumbnail", "base_price", "seller_name",
            "is_featured", "average_rating", "review_count", "sales_count",
            "created_at",
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    """Full product serializer for detail views."""

    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    licenses = LicenseSerializer(many=True, read_only=True)
    previews = ProductPreviewSerializer(many=True, read_only=True)
    files = serializers.SerializerMethodField()
    seller = UserSerializer(read_only=True)
    seller_name = serializers.ReadOnlyField()
    base_price = serializers.ReadOnlyField()

    class Meta:
        model = DigitalProduct
        fields = (
            "id", "title", "slug", "description", "short_description",
            "product_type", "category", "tags", "thumbnail", "status",
            "is_featured", "version", "file_formats", "compatibility",
            "meta_title", "meta_description",
            "view_count", "download_count", "sales_count",
            "average_rating", "review_count",
            "licenses", "previews", "files",
            "seller", "seller_name", "base_price",
            "created_at", "updated_at", "published_at",
        )

    def get_files(self, obj):
        """Only show file details to the product owner."""
        request = self.context.get("request")
        if request and request.user == obj.seller:
            return ProductFileSerializer(obj.files.all(), many=True).data
        # For buyers, just show file count and total size
        files = obj.files.all()
        total_size = sum(f.file_size for f in files)
        return {
            "count": files.count(),
            "total_size": total_size,
            "formats": obj.file_formats,
        }


class ProductCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating products."""

    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        write_only=True,
    )
    licenses_data = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = DigitalProduct
        fields = (
            "title", "description", "short_description", "product_type",
            "category", "tags", "thumbnail", "version",
            "file_formats", "compatibility",
            "meta_title", "meta_description", "licenses_data",
        )

    def create(self, validated_data):
        tags_data = validated_data.pop("tags", [])
        licenses_data = validated_data.pop("licenses_data", [])
        request = self.context["request"]
        validated_data["seller"] = request.user

        product = DigitalProduct.objects.create(**validated_data)

        # Handle tags
        for tag_name in tags_data:
            tag, _ = Tag.objects.get_or_create(
                name=tag_name,
                defaults={"slug": tag_name.lower().replace(" ", "-")},
            )
            product.tags.add(tag)

        # Handle licenses
        for license_data in licenses_data:
            License.objects.create(product=product, **license_data)

        return product

    def update(self, instance, validated_data):
        tags_data = validated_data.pop("tags", None)
        licenses_data = validated_data.pop("licenses_data", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tags_data is not None:
            instance.tags.clear()
            for tag_name in tags_data:
                tag, _ = Tag.objects.get_or_create(
                    name=tag_name,
                    defaults={"slug": tag_name.lower().replace(" ", "-")},
                )
                instance.tags.add(tag)

        if licenses_data is not None:
            instance.licenses.all().delete()
            for license_data in licenses_data:
                License.objects.create(product=instance, **license_data)

        return instance
