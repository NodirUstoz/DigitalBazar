"""
Product models: DigitalProduct, Category, Tag, ProductFile, ProductPreview, License.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """Product category with hierarchical support."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    description = models.TextField(max_length=500, blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class name")
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "categories"
        ordering = ["sort_order", "name"]
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def product_count(self):
        return self.products.filter(status=DigitalProduct.Status.PUBLISHED).count()


class Tag(models.Model):
    """Tags for product categorization and search."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, db_index=True)

    class Meta:
        db_table = "tags"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class DigitalProduct(models.Model):
    """
    Core product model for the marketplace.
    Represents any digital product that can be bought and downloaded.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending Review"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    class ProductType(models.TextChoices):
        SOFTWARE = "software", "Software / Plugin"
        TEMPLATE = "template", "Template"
        THEME = "theme", "Theme"
        GRAPHICS = "graphics", "Graphics / Design"
        MUSIC = "music", "Music / Audio"
        FONT = "font", "Font"
        COURSE = "course", "Course"
        EBOOK = "ebook", "E-Book / Document"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="products",
    )
    title = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=280, unique=True, db_index=True)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)
    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        default=ProductType.OTHER,
        db_index=True,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name="products",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="products")
    thumbnail = models.ImageField(
        upload_to="products/thumbnails/%Y/%m/", blank=True, null=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    is_featured = models.BooleanField(default=False, db_index=True)
    version = models.CharField(max_length=20, blank=True, default="1.0")
    file_formats = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated file formats, e.g. 'PSD, AI, PNG'"
    )
    compatibility = models.CharField(
        max_length=255, blank=True,
        help_text="Software compatibility info"
    )

    # SEO fields
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    # Statistics (denormalized for performance)
    view_count = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)
    sales_count = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.00
    )
    review_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "digital_products"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "product_type"]),
            models.Index(fields=["-sales_count"]),
            models.Index(fields=["-average_rating"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while DigitalProduct.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def base_price(self):
        """Returns the lowest license price for this product."""
        license_obj = self.licenses.filter(is_active=True).order_by("price").first()
        return license_obj.price if license_obj else None

    @property
    def seller_name(self):
        try:
            return self.seller.seller_profile.store_name
        except Exception:
            return self.seller.username


class License(models.Model):
    """
    License tiers for a product. Each product can have multiple licenses
    at different price points with different rights.
    """

    class LicenseType(models.TextChoices):
        PERSONAL = "personal", "Personal License"
        COMMERCIAL = "commercial", "Commercial License"
        EXTENDED = "extended", "Extended License"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        DigitalProduct,
        on_delete=models.CASCADE,
        related_name="licenses",
    )
    license_type = models.CharField(
        max_length=20,
        choices=LicenseType.choices,
        default=LicenseType.PERSONAL,
    )
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    features = models.JSONField(
        default=list,
        help_text="List of features included in this license tier.",
    )
    max_downloads = models.PositiveIntegerField(
        default=1,
        help_text="Maximum number of downloads allowed. 0 for unlimited.",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "licenses"
        ordering = ["sort_order", "price"]
        unique_together = ["product", "license_type"]

    def __str__(self):
        return f"{self.product.title} - {self.name} (${self.price})"


class ProductFile(models.Model):
    """
    Downloadable files attached to a product.
    Stored securely with access control.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        DigitalProduct,
        on_delete=models.CASCADE,
        related_name="files",
    )
    file = models.FileField(upload_to="products/files/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField(default=0, help_text="File size in bytes")
    file_hash = models.CharField(max_length=64, blank=True, help_text="SHA-256 hash")
    version = models.CharField(max_length=20, default="1.0")
    is_main = models.BooleanField(
        default=False, help_text="Primary downloadable file"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_files"
        ordering = ["-is_main", "-uploaded_at"]

    def __str__(self):
        return f"{self.original_filename} ({self.product.title})"

    @property
    def file_size_display(self):
        size = self.file_size
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class ProductPreview(models.Model):
    """
    Preview media for a product (screenshots, audio samples, demo videos).
    """

    class PreviewType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"
        DOCUMENT = "document", "Document"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        DigitalProduct,
        on_delete=models.CASCADE,
        related_name="previews",
    )
    preview_type = models.CharField(
        max_length=20,
        choices=PreviewType.choices,
        default=PreviewType.IMAGE,
    )
    file = models.FileField(upload_to="products/previews/%Y/%m/")
    title = models.CharField(max_length=255, blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_previews"
        ordering = ["sort_order"]

    def __str__(self):
        return f"{self.preview_type}: {self.product.title}"
