"""
Account serializers for registration, authentication, and profile management.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify
from rest_framework import serializers

from .models import SellerProfile, BuyerProfile

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""

    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = (
            "email", "username", "password", "password_confirm",
            "first_name", "last_name", "role",
        )

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        role = attrs.get("role", User.Role.BUYER)
        if role == User.Role.ADMIN:
            raise serializers.ValidationError(
                {"role": "Cannot register as admin."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()

        if user.role == User.Role.SELLER:
            SellerProfile.objects.create(
                user=user,
                store_name=user.username,
                store_slug=slugify(user.username),
            )
        elif user.role in (User.Role.BUYER, User.Role.AFFILIATE):
            BuyerProfile.objects.create(user=user)

        return user


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile data."""

    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = (
            "id", "email", "username", "first_name", "last_name",
            "full_name", "role", "avatar", "bio", "is_verified",
            "date_joined",
        )
        read_only_fields = ("id", "email", "role", "is_verified", "date_joined")


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "avatar", "bio")

    def validate_username(self, value):
        user = self.context["request"].user
        if User.objects.exclude(pk=user.pk).filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password."""

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True, validators=[validate_password]
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value


class SellerProfileSerializer(serializers.ModelSerializer):
    """Serializer for seller profile data."""

    user = UserSerializer(read_only=True)
    product_count = serializers.IntegerField(
        source="total_products", read_only=True
    )

    class Meta:
        model = SellerProfile
        fields = (
            "id", "user", "store_name", "store_slug", "store_description",
            "store_logo", "store_banner", "website", "verification_status",
            "total_sales", "total_revenue", "product_count", "rating",
            "created_at",
        )
        read_only_fields = (
            "id", "verification_status", "total_sales", "total_revenue",
            "rating", "created_at",
        )


class SellerProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating seller profile."""

    class Meta:
        model = SellerProfile
        fields = (
            "store_name", "store_slug", "store_description",
            "store_logo", "store_banner", "website",
        )

    def validate_store_name(self, value):
        profile = self.instance
        qs = SellerProfile.objects.exclude(pk=profile.pk).filter(store_name=value)
        if qs.exists():
            raise serializers.ValidationError("This store name is already taken.")
        return value

    def validate_store_slug(self, value):
        profile = self.instance
        qs = SellerProfile.objects.exclude(pk=profile.pk).filter(store_slug=value)
        if qs.exists():
            raise serializers.ValidationError("This store slug is already taken.")
        return value


class BuyerProfileSerializer(serializers.ModelSerializer):
    """Serializer for buyer profile data."""

    user = UserSerializer(read_only=True)

    class Meta:
        model = BuyerProfile
        fields = (
            "id", "user", "phone", "total_purchases",
            "total_spent", "created_at",
        )
        read_only_fields = (
            "id", "total_purchases", "total_spent", "created_at",
        )
