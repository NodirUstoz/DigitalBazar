"""
Account admin configuration.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, SellerProfile, BuyerProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "email", "username", "role", "is_active",
        "is_verified", "date_joined",
    )
    list_filter = ("role", "is_active", "is_verified", "is_staff")
    search_fields = ("email", "username", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "updated_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": (
            "username", "first_name", "last_name", "avatar", "bio",
        )}),
        ("Roles & Permissions", {"fields": (
            "role", "is_active", "is_staff", "is_superuser",
            "is_verified", "groups", "user_permissions",
        )}),
        ("Dates", {"fields": ("date_joined", "updated_at", "last_login")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "username", "password1", "password2",
                "role", "is_active", "is_staff",
            ),
        }),
    )


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "store_name", "user", "verification_status",
        "total_sales", "total_revenue", "rating",
    )
    list_filter = ("verification_status",)
    search_fields = ("store_name", "user__email")
    readonly_fields = (
        "total_sales", "total_revenue", "total_products",
        "rating", "created_at", "updated_at",
    )
    prepopulated_fields = {"store_slug": ("store_name",)}


@admin.register(BuyerProfile)
class BuyerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "total_purchases", "total_spent", "created_at")
    search_fields = ("user__email",)
    readonly_fields = ("total_purchases", "total_spent", "created_at", "updated_at")
