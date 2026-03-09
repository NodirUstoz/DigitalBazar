"""
Celery tasks for order processing, payouts, and reporting.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.db.models import Sum, Count, F
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_order_completion(self, order_id):
    """
    Process a completed order:
    - Generate license keys
    - Update product statistics
    - Update seller/buyer profiles
    - Handle affiliate commissions
    """
    from apps.orders.models import Order, LicenseKey
    from apps.products.models import DigitalProduct
    from apps.accounts.models import SellerProfile, BuyerProfile
    from apps.affiliates.models import Commission
    from utils.license_generator import generate_license_key

    try:
        order = Order.objects.prefetch_related(
            "items", "items__product", "items__license"
        ).get(id=order_id)

        if order.status != Order.Status.COMPLETED:
            logger.warning(f"Order {order_id} is not completed, skipping processing.")
            return

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

            # Update product stats
            if item.product:
                DigitalProduct.objects.filter(pk=item.product.pk).update(
                    sales_count=F("sales_count") + 1
                )

            # Update seller profile
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
        if order.affiliate_link:
            affiliate_link = order.affiliate_link
            program = affiliate_link.program
            if program.is_active:
                commission_amount = (
                    order.subtotal * Decimal(str(program.commission_rate)) / Decimal("100")
                ).quantize(Decimal("0.01"))

                if commission_amount >= Decimal("1.00"):
                    Commission.objects.create(
                        affiliate=affiliate_link.affiliate,
                        affiliate_link=affiliate_link,
                        order=order,
                        amount=commission_amount,
                        status=Commission.Status.PENDING,
                    )

        logger.info(f"Order {order.order_number} processing completed.")

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found.")
    except Exception as exc:
        logger.error(f"Error processing order {order_id}: {exc}")
        self.retry(exc=exc, countdown=60)


@shared_task
def process_pending_payouts():
    """
    Process pending seller payouts.
    Runs daily via Celery Beat.
    """
    from apps.payments.models import SellerPayout
    from apps.orders.models import OrderItem
    from apps.accounts.models import SellerProfile

    sellers = SellerProfile.objects.filter(
        stripe_onboarding_complete=True,
        verification_status=SellerProfile.VerificationStatus.VERIFIED,
    )

    minimum_payout = Decimal(str(settings.MINIMUM_PAYOUT_AMOUNT))

    for seller_profile in sellers:
        # Calculate unpaid earnings
        unpaid_items = OrderItem.objects.filter(
            seller=seller_profile.user,
            order__status="completed",
            is_refunded=False,
        ).exclude(
            id__in=SellerPayout.objects.filter(
                seller=seller_profile.user,
                status__in=["completed", "processing"],
            ).values_list("items__id", flat=True)
        )

        total_unpaid = unpaid_items.aggregate(
            total=Sum("seller_amount")
        )["total"] or Decimal("0.00")

        if total_unpaid >= minimum_payout:
            payout = SellerPayout.objects.create(
                seller=seller_profile.user,
                amount=total_unpaid,
                status=SellerPayout.Status.PENDING,
            )
            logger.info(
                f"Created payout {payout.id} for seller "
                f"{seller_profile.user.email}: ${total_unpaid}"
            )


@shared_task
def generate_daily_sales_report():
    """Generate daily sales report for analytics."""
    from apps.analytics.models import SalesReport
    from apps.orders.models import Order

    yesterday = timezone.now().date() - timedelta(days=1)

    orders = Order.objects.filter(
        status=Order.Status.COMPLETED,
        completed_at__date=yesterday,
    )

    report_data = orders.aggregate(
        total_orders=Count("id"),
        total_revenue=Sum("total"),
        total_platform_fees=Sum("platform_fee"),
    )

    SalesReport.objects.update_or_create(
        report_date=yesterday,
        report_type=SalesReport.ReportType.DAILY,
        defaults={
            "total_orders": report_data["total_orders"] or 0,
            "total_revenue": report_data["total_revenue"] or Decimal("0.00"),
            "total_platform_fees": report_data["total_platform_fees"] or Decimal("0.00"),
            "total_seller_earnings": (
                (report_data["total_revenue"] or Decimal("0.00"))
                - (report_data["total_platform_fees"] or Decimal("0.00"))
            ),
        },
    )

    logger.info(f"Daily sales report generated for {yesterday}")


@shared_task
def cleanup_expired_downloads():
    """Clean up expired download tokens and temp files."""
    from apps.orders.models import LicenseKey

    expired = LicenseKey.objects.filter(
        expires_at__lt=timezone.now(),
        status=LicenseKey.Status.ACTIVE,
    )
    count = expired.update(status=LicenseKey.Status.EXPIRED)
    logger.info(f"Expired {count} license keys.")


@shared_task
def update_product_statistics():
    """Update denormalized product statistics from order data."""
    from apps.products.models import DigitalProduct
    from apps.orders.models import OrderItem
    from apps.reviews.models import Review

    products = DigitalProduct.objects.filter(
        status=DigitalProduct.Status.PUBLISHED
    )

    for product in products:
        sales_count = OrderItem.objects.filter(
            product=product,
            order__status="completed",
            is_refunded=False,
        ).count()

        download_count = product.files.aggregate(
            total=Sum("downloads__id")
        )["total"] or 0

        reviews = Review.objects.filter(product=product, is_approved=True)
        review_count = reviews.count()
        avg_rating = reviews.aggregate(
            avg=models.Avg("rating")
        )["avg"] or Decimal("0.00")

        DigitalProduct.objects.filter(pk=product.pk).update(
            sales_count=sales_count,
            download_count=download_count,
            review_count=review_count,
            average_rating=round(avg_rating, 2),
        )

    logger.info(f"Updated statistics for {products.count()} products.")
