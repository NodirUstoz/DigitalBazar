"""
Order service layer for DigitalBazar.
Orchestrates the complete order lifecycle: creation, fulfillment,
cancellation, and post-purchase operations.
"""

import logging
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import BuyerProfile, SellerProfile
from apps.affiliates.models import AffiliateLink, Commission
from apps.products.models import DigitalProduct, License, ProductFile
from utils.license_generator import generate_license_key, generate_download_token
from .models import Download, LicenseKey, Order, OrderItem

logger = logging.getLogger(__name__)


class OrderService:
    """Handles the complete order lifecycle."""

    @staticmethod
    @transaction.atomic
    def create_order(buyer, cart_items: list, affiliate_code: str = "") -> Order:
        """
        Create an order from validated cart items.

        Args:
            buyer: The authenticated User placing the order.
            cart_items: List of dicts with 'product' and 'license' keys.
            affiliate_code: Optional affiliate referral code.

        Returns:
            The created Order instance.

        Raises:
            ValueError: If cart is empty or contains invalid items.
        """
        if not cart_items:
            raise ValueError("Cart is empty.")

        affiliate_link = None
        if affiliate_code:
            try:
                affiliate_link = AffiliateLink.objects.get(
                    code=affiliate_code, is_active=True
                )
            except AffiliateLink.DoesNotExist:
                logger.info("Invalid affiliate code ignored: %s", affiliate_code)

        subtotal = sum(item["license"].price for item in cart_items)

        order = Order.objects.create(
            buyer=buyer,
            subtotal=subtotal,
            total=subtotal,
            affiliate_link=affiliate_link,
        )

        platform_fee_total = Decimal("0.00")

        for item in cart_items:
            product = item["product"]
            license_obj = item["license"]
            seller = product.seller

            commission_rate = _get_seller_commission_rate(seller)
            platform_fee = (
                license_obj.price * commission_rate / Decimal("100")
            ).quantize(Decimal("0.01"))
            seller_amount = license_obj.price - platform_fee
            platform_fee_total += platform_fee

            OrderItem.objects.create(
                order=order,
                product=product,
                license=license_obj,
                seller=seller,
                product_title=product.title,
                license_name=license_obj.name,
                price=license_obj.price,
                seller_amount=seller_amount,
                platform_fee=platform_fee,
            )

        order.platform_fee = platform_fee_total
        order.save(update_fields=["platform_fee"])

        logger.info("Order %s created with %d items", order.order_number, len(cart_items))
        return order

    @staticmethod
    @transaction.atomic
    def fulfill_order(order_id: str) -> bool:
        """
        Fulfill a completed order by generating license keys
        and updating all relevant statistics.

        Args:
            order_id: UUID of the order to fulfill.

        Returns:
            True if fulfillment succeeded.
        """
        try:
            order = Order.objects.prefetch_related(
                "items", "items__product", "items__license"
            ).get(id=order_id, status=Order.Status.COMPLETED)
        except Order.DoesNotExist:
            logger.error("Cannot fulfill: order %s not found or not completed.", order_id)
            return False

        for item in order.items.all():
            # Generate license key
            max_downloads = item.license.max_downloads if item.license else 1
            key = generate_license_key()

            LicenseKey.objects.create(
                order_item=item,
                buyer=order.buyer,
                key=key,
                max_downloads=max_downloads,
            )

            # Update product sales count
            if item.product:
                DigitalProduct.objects.filter(pk=item.product.pk).update(
                    sales_count=F("sales_count") + 1
                )

            # Update seller profile stats
            if item.seller:
                SellerProfile.objects.filter(user=item.seller).update(
                    total_sales=F("total_sales") + 1,
                    total_revenue=F("total_revenue") + item.seller_amount,
                )

        # Update buyer profile
        BuyerProfile.objects.filter(user=order.buyer).update(
            total_purchases=F("total_purchases") + 1,
            total_spent=F("total_spent") + order.total,
        )

        # Handle affiliate commission
        _process_affiliate_commission(order)

        logger.info("Order %s fulfilled successfully.", order.order_number)
        return True

    @staticmethod
    def generate_secure_download_url(
        license_key: LicenseKey,
        product_file: ProductFile,
        user,
    ) -> Optional[str]:
        """
        Generate a secure, time-limited download token for a purchased file.

        Returns:
            The download token string, or None if not authorized.
        """
        if license_key.buyer != user:
            logger.warning(
                "Download denied: user %s is not owner of license %s",
                user.id, license_key.id,
            )
            return None

        if not license_key.is_valid:
            logger.warning(
                "Download denied: license %s is not valid (status=%s, downloads=%d/%d)",
                license_key.id, license_key.status,
                license_key.download_count, license_key.max_downloads,
            )
            return None

        token = generate_download_token(
            license_key_id=str(license_key.id),
            file_id=str(product_file.id),
            user_id=str(user.id),
            secret=settings.SECRET_KEY,
        )
        return token

    @staticmethod
    @transaction.atomic
    def record_download(license_key: LicenseKey, product_file: ProductFile, request) -> Download:
        """
        Record a file download and increment counters.
        """
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = x_forwarded.split(",")[0].strip() if x_forwarded else request.META.get("REMOTE_ADDR")

        download = Download.objects.create(
            license_key=license_key,
            buyer=license_key.buyer,
            product_file=product_file,
            ip_address=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        # Increment license download count
        LicenseKey.objects.filter(pk=license_key.pk).update(
            download_count=F("download_count") + 1
        )

        # Increment product download count
        DigitalProduct.objects.filter(pk=product_file.product_id).update(
            download_count=F("download_count") + 1
        )

        return download

    @staticmethod
    @transaction.atomic
    def cancel_order(order_id: str, reason: str = "") -> bool:
        """Cancel a pending or processing order before payment completes."""
        try:
            order = Order.objects.get(
                id=order_id,
                status__in=[Order.Status.PENDING, Order.Status.PROCESSING],
            )
        except Order.DoesNotExist:
            return False

        order.status = Order.Status.FAILED
        order.notes = f"Cancelled: {reason}" if reason else "Cancelled by user."
        order.save(update_fields=["status", "notes"])

        logger.info("Order %s cancelled: %s", order.order_number, reason)
        return True


def _get_seller_commission_rate(seller) -> Decimal:
    """Retrieve the commission rate for a seller."""
    try:
        return seller.seller_profile.commission_rate
    except (SellerProfile.DoesNotExist, AttributeError):
        return Decimal(str(settings.PLATFORM_COMMISSION))


def _process_affiliate_commission(order: Order):
    """Create an affiliate commission if the order has a referral."""
    if not order.affiliate_link:
        return

    link = order.affiliate_link
    program = link.program

    if not program.is_active:
        return

    commission_amount = (
        order.subtotal * Decimal(str(program.commission_rate)) / Decimal("100")
    ).quantize(Decimal("0.01"))

    if commission_amount < Decimal("1.00"):
        return

    Commission.objects.create(
        affiliate=link.affiliate,
        affiliate_link=link,
        order=order,
        amount=commission_amount,
        status=Commission.Status.PENDING,
    )

    # Update link stats
    AffiliateLink.objects.filter(pk=link.pk).update(
        conversion_count=F("conversion_count") + 1,
        total_earned=F("total_earned") + commission_amount,
    )

    logger.info(
        "Affiliate commission $%s created for %s on order %s",
        commission_amount, link.affiliate.email, order.order_number,
    )
