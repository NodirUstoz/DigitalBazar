"""
Product filters for advanced search and filtering.
"""

import django_filters
from .models import DigitalProduct


class ProductFilter(django_filters.FilterSet):
    """Filter set for product listing with advanced search capabilities."""

    title = django_filters.CharFilter(lookup_expr="icontains")
    category = django_filters.UUIDFilter(field_name="category__id")
    category_slug = django_filters.CharFilter(field_name="category__slug")
    product_type = django_filters.ChoiceFilter(
        choices=DigitalProduct.ProductType.choices
    )
    min_price = django_filters.NumberFilter(
        field_name="licenses__price", lookup_expr="gte"
    )
    max_price = django_filters.NumberFilter(
        field_name="licenses__price", lookup_expr="lte"
    )
    min_rating = django_filters.NumberFilter(
        field_name="average_rating", lookup_expr="gte"
    )
    seller = django_filters.UUIDFilter(field_name="seller__id")
    tag = django_filters.CharFilter(field_name="tags__slug")
    is_featured = django_filters.BooleanFilter()

    ordering = django_filters.OrderingFilter(
        fields=(
            ("created_at", "newest"),
            ("sales_count", "popular"),
            ("average_rating", "rating"),
            ("licenses__price", "price"),
        ),
    )

    class Meta:
        model = DigitalProduct
        fields = [
            "title", "category", "category_slug", "product_type",
            "min_price", "max_price", "min_rating", "seller",
            "tag", "is_featured",
        ]
