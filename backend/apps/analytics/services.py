"""
Analytics service layer for DigitalBazar.
Handles data aggregation, report generation, and event tracking.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Count, F, Sum, Q
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone

from apps.accounts.models import User, SellerProfile
from apps.orders.models import Order, OrderItem
from apps.products.models import DigitalProduct
from .models import ProductView, DownloadStat, SalesReport

logger = logging.getLogger(__name__)

CACHE_TTL_DASHBOARD = 300   # 5 minutes
CACHE_TTL_REPORT = 3600     # 1 hour


class AnalyticsService:
    """Central service for analytics data operations."""

    @staticmethod
    def track_product_view(product, request):
        """
        Record a product page view event.
        Deduplicates views from the same session within a 30-minute window.
        """
        session_id = request.session.session_key or ""
        ip = _get_client_ip(request)

        # Dedup: same session + product within 30 mins
        thirty_min_ago = timezone.now() - timedelta(minutes=30)
        recent_exists = ProductView.objects.filter(
            product=product,
            session_id=session_id,
            viewed_at__gte=thirty_min_ago,
        ).exists()

        if recent_exists and session_id:
            return None

        view = ProductView.objects.create(
            product=product,
            viewer=request.user if request.user.is_authenticated else None,
            ip_address=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            referrer=request.META.get("HTTP_REFERER", "")[:200],
            session_id=session_id,
        )
        return view

    @staticmethod
    def get_seller_dashboard(seller_id: str) -> dict:
        """
        Compute seller dashboard metrics with caching.
        Returns revenue, sales, views, products, and trend data.
        """
        cache_key = f"dashboard:seller:{seller_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        products = DigitalProduct.objects.filter(
            seller_id=seller_id
        ).exclude(status=DigitalProduct.Status.ARCHIVED)

        product_stats = products.aggregate(
            total_views=Sum("view_count"),
            total_downloads=Sum("download_count"),
            avg_rating=Avg("average_rating"),
        )

        completed_items = OrderItem.objects.filter(
            seller_id=seller_id,
            order__status=Order.Status.COMPLETED,
            is_refunded=False,
        )

        total_revenue = completed_items.aggregate(
            total=Sum("seller_amount")
        )["total"] or Decimal("0.00")

        recent_revenue = completed_items.filter(
            order__completed_at__gte=thirty_days_ago
        ).aggregate(
            total=Sum("seller_amount")
        )["total"] or Decimal("0.00")

        data = {
            "total_products": products.count(),
            "total_revenue": str(total_revenue),
            "recent_revenue": str(recent_revenue),
            "total_sales": completed_items.count(),
            "total_views": product_stats["total_views"] or 0,
            "total_downloads": product_stats["total_downloads"] or 0,
            "average_rating": str(round(product_stats["avg_rating"] or 0, 2)),
        }

        cache.set(cache_key, data, CACHE_TTL_DASHBOARD)
        return data

    @staticmethod
    def get_revenue_timeseries(
        seller_id: str,
        days: int = 30,
        group_by: str = "day",
    ) -> list:
        """
        Generate a revenue time series for charting.
        Groups data by day, week, or month.
        """
        start_date = timezone.now() - timedelta(days=days)

        items = OrderItem.objects.filter(
            seller_id=seller_id,
            order__status=Order.Status.COMPLETED,
            order__completed_at__gte=start_date,
            is_refunded=False,
        )

        trunc_map = {
            "day": TruncDate,
            "week": TruncWeek,
            "month": TruncMonth,
        }
        trunc_func = trunc_map.get(group_by, TruncDate)

        data = (
            items
            .annotate(period=trunc_func("order__completed_at"))
            .values("period")
            .annotate(
                revenue=Sum("seller_amount"),
                orders=Count("id"),
                fees=Sum("platform_fee"),
            )
            .order_by("period")
        )

        return [
            {
                "period": entry["period"].isoformat(),
                "revenue": str(entry["revenue"]),
                "orders": entry["orders"],
                "fees": str(entry["fees"]),
            }
            for entry in data
        ]

    @staticmethod
    def generate_sales_report(
        report_date: date,
        report_type: str = "daily",
        seller: Optional[User] = None,
    ) -> SalesReport:
        """
        Generate or update a sales report for the given date and scope.
        Can generate per-seller or platform-wide reports.
        """
        filters = {
            "status": Order.Status.COMPLETED,
        }

        if report_type == "daily":
            filters["completed_at__date"] = report_date
        elif report_type == "weekly":
            week_start = report_date - timedelta(days=report_date.weekday())
            filters["completed_at__date__gte"] = week_start
            filters["completed_at__date__lte"] = week_start + timedelta(days=6)
        elif report_type == "monthly":
            filters["completed_at__year"] = report_date.year
            filters["completed_at__month"] = report_date.month

        orders = Order.objects.filter(**filters)

        if seller:
            items = OrderItem.objects.filter(
                order__in=orders, seller=seller, is_refunded=False
            )
            agg = items.aggregate(
                total_revenue=Sum("price"),
                total_fees=Sum("platform_fee"),
                total_earnings=Sum("seller_amount"),
                total_orders=Count("order", distinct=True),
            )
        else:
            agg = orders.aggregate(
                total_revenue=Sum("total"),
                total_fees=Sum("platform_fee"),
                total_orders=Count("id"),
            )
            agg["total_earnings"] = (
                (agg["total_revenue"] or Decimal("0.00"))
                - (agg["total_fees"] or Decimal("0.00"))
            )

        # Top products by revenue
        top_products = list(
            OrderItem.objects.filter(
                order__in=orders,
                is_refunded=False,
                **({"seller": seller} if seller else {}),
            )
            .values("product__title")
            .annotate(revenue=Sum("price"), count=Count("id"))
            .order_by("-revenue")[:5]
        )

        report, _ = SalesReport.objects.update_or_create(
            report_date=report_date,
            report_type=report_type,
            seller=seller,
            defaults={
                "total_orders": agg["total_orders"] or 0,
                "total_revenue": agg["total_revenue"] or Decimal("0.00"),
                "total_platform_fees": agg["total_fees"] or Decimal("0.00"),
                "total_seller_earnings": agg["total_earnings"] or Decimal("0.00"),
                "top_products": [
                    {"title": p["product__title"], "revenue": str(p["revenue"]), "sales": p["count"]}
                    for p in top_products
                ],
            },
        )

        logger.info(
            "Generated %s report for %s on %s",
            report_type,
            seller.email if seller else "platform",
            report_date,
        )
        return report

    @staticmethod
    def update_download_stats(product_id: str):
        """
        Update the aggregated download statistics for a product.
        Called after each download event.
        """
        from apps.orders.models import Download

        today = timezone.now().date()

        total_today = Download.objects.filter(
            product_file__product_id=product_id,
            downloaded_at__date=today,
        ).count()

        unique_today = (
            Download.objects.filter(
                product_file__product_id=product_id,
                downloaded_at__date=today,
            )
            .values("buyer")
            .distinct()
            .count()
        )

        DownloadStat.objects.update_or_create(
            product_id=product_id,
            date=today,
            defaults={
                "download_count": total_today,
                "unique_downloaders": unique_today,
            },
        )


def _get_client_ip(request):
    """Extract client IP from the request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
