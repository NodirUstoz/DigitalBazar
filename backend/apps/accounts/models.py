"""
Account models: User, SellerProfile, BuyerProfile.
"""

import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom user manager supporting email-based authentication."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model using email for authentication.
    Supports multiple roles: Admin, Seller, Buyer, Affiliate.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        SELLER = "seller", "Seller"
        BUYER = "buyer", "Buyer"
        AFFILIATE = "affiliate", "Affiliate"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, max_length=255, db_index=True)
    username = models.CharField(max_length=150, unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.BUYER,
        db_index=True,
    )
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", blank=True, null=True)
    bio = models.TextField(max_length=1000, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"
        ordering = ["-date_joined"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    @property
    def is_seller(self):
        return self.role in (self.Role.SELLER, self.Role.ADMIN)

    @property
    def is_buyer(self):
        return self.role in (self.Role.BUYER, self.Role.ADMIN)

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN


class SellerProfile(models.Model):
    """
    Extended profile for users with the Seller role.
    Contains store information, payout details, and verification status.
    """

    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="seller_profile",
    )
    store_name = models.CharField(max_length=255, unique=True)
    store_slug = models.SlugField(max_length=255, unique=True, db_index=True)
    store_description = models.TextField(max_length=2000, blank=True)
    store_logo = models.ImageField(
        upload_to="store_logos/%Y/%m/", blank=True, null=True
    )
    store_banner = models.ImageField(
        upload_to="store_banners/%Y/%m/", blank=True, null=True
    )
    website = models.URLField(blank=True)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    stripe_account_id = models.CharField(max_length=255, blank=True)
    stripe_onboarding_complete = models.BooleanField(default=False)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15.00,
        help_text="Platform commission percentage for this seller.",
    )
    total_sales = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    total_products = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.00
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "seller_profiles"
        verbose_name = "Seller Profile"
        verbose_name_plural = "Seller Profiles"

    def __str__(self):
        return f"{self.store_name} ({self.user.email})"


class BuyerProfile(models.Model):
    """
    Extended profile for users with the Buyer role.
    Tracks purchase history and preferences.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="buyer_profile",
    )
    shipping_address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    total_purchases = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    favorite_categories = models.ManyToManyField(
        "products.Category", blank=True, related_name="interested_buyers"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "buyer_profiles"
        verbose_name = "Buyer Profile"
        verbose_name_plural = "Buyer Profiles"

    def __str__(self):
        return f"Buyer: {self.user.email}"
