"""
Analytics views: dashboard, sales data, product performance, download stats.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order, OrderItem
from apps.products.models import DigitalProduct
from .models import ProductView, DownloadStat, SalesReport
from .serializers import (
    ProductViewSerializer, DownloadStatSerializer,
    SalesReportSerializer,
)


class DashboardView(APIView):
    """
    Seller dashboard summary with key metrics.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        if not request.user.is_seller:
            return Response(
                {"detail": "You are not a seller."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = request.user
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        # Product stats
        products = DigitalProduct.objects.filter(
            seller=user
        ).exclude(status=DigitalProduct.Status.ARCHIVED)

        total_products = products.count()
        product_stats = products.aggregate(
            total_views=Sum("view_count"),
            total_downloads=Sum("download_count"),
            avg_rating=Avg("average_rating"),
        )

        # Sales stats
        completed_items = OrderItem.objects.filter(
            seller=user,
            order__status=Order.Status.COMPLETED,
            is_refunded=False,
        )

        total_sales = completed_items.count()
        total_revenue = completed_items.aggregate(
            total=Sum("seller_amount")
        )["total"] or Decimal("0.00")

        # Revenue chart data (last 30 days, grouped by day)
        revenue_by_day = (
            completed_items
            .filter(order__completed_at__gte=thirty_days_ago)
            .annotate(date=TruncDate("order__completed_at"))
            .values("date")
            .annotate(
                revenue=Sum("seller_amount"),
                count=Count("id"),
            )
            .order_by("date")
        )

        revenue_chart = [
            {
                "date": entry["date"].isoformat(),
                "revenue": str(entry["revenue"]),
                "orders": entry["count"],
            }
            for entry in revenue_by_day
        ]

        # Recent orders
        recent_orders = (
            Order.objects
            .filter(items__seller=user)
            .distinct()
            .order_by("-created_at")[:10]
        )
        recent_orders_data = [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "total": str(o.total),
                "status": o.status,
                "created_at": o.created_at.isoformat(),
            }
            for o in recent_orders
        ]

        # Monthly revenue comparison
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

        this_month_revenue = (
            completed_items
            .filter(order__completed_at__gte=this_month_start)
            .aggregate(total=Sum("seller_amount"))["total"]
            or Decimal("0.00")
        )

        last_month_revenue = (
            completed_items
            .filter(
                order__completed_at__gte=last_month_start,
                order__completed_at__lt=this_month_start,
            )
            .aggregate(total=Sum("seller_amount"))["total"]
            or Decimal("0.00")
        )

        if last_month_revenue > 0:
            revenue_change = round(
                ((this_month_revenue - last_month_revenue) / last_month_revenue) * 100, 1
            )
        else:
            revenue_change = 100 if this_month_revenue > 0 else 0

        return Response({
            "total_revenue": str(total_revenue),
            "total_sales": total_sales,
            "total_products": total_products,
            "total_downloads": product_stats["total_downloads"] or 0,
            "total_views": product_stats["total_views"] or 0,
            "average_rating": str(round(product_stats["avg_rating"] or 0, 2)),
            "this_month_revenue": str(this_month_revenue),
            "revenue_change_percent": revenue_change,
            "recent_orders": recent_orders_data,
            "revenue_chart": revenue_chart,
        })


class SalesDataView(APIView):
    """
    Detailed sales data for the seller with time range filtering.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        if not request.user.is_seller:
            return Response(
                {"detail": "You are not a seller."},
                status=status.HTTP_403_FORBIDDEN,
            )

        period = request.query_params.get("period", "30d")
        group_by = request.query_params.get("group_by", "day")

        now = timezone.now()
        if period == "7d":
            start_date = now - timedelta(days=7)
        elif period == "30d":
            start_date = now - timedelta(days=30)
        elif period == "90d":
            start_date = now - timedelta(days=90)
        elif period == "1y":
            start_date = now - timedelta(days=365)
        else:
            start_date = now - timedelta(days=30)

        items = OrderItem.objects.filter(
            seller=request.user,
            order__status=Order.Status.COMPLETED,
            order__completed_at__gte=start_date,
            is_refunded=False,
        )

        if group_by == "week":
            trunc_func = TruncWeek
        elif group_by == "month":
            trunc_func = TruncMonth
        else:
            trunc_func = TruncDate

        sales_data = (
            items
            .annotate(period=trunc_func("order__completed_at"))
            .values("period")
            .annotate(
                revenue=Sum("seller_amount"),
                orders=Count("id"),
                platform_fees=Sum("platform_fee"),
            )
            .order_by("period")
        )

        result = [
            {
                "period": entry["period"].isoformat(),
                "revenue": str(entry["revenue"]),
                "orders": entry["orders"],
                "platform_fees": str(entry["platform_fees"]),
            }
            for entry in sales_data
        ]

        # Totals
        totals = items.aggregate(
            total_revenue=Sum("seller_amount"),
            total_orders=Count("id"),
            total_fees=Sum("platform_fee"),
        )

        return Response({
            "period": period,
            "group_by": group_by,
            "data": result,
            "totals": {
                "revenue": str(totals["total_revenue"] or Decimal("0.00")),
                "orders": totals["total_orders"] or 0,
                "platform_fees": str(totals["total_fees"] or Decimal("0.00")),
            },
        })


class ProductPerformanceView(APIView):
    """
    Product performance metrics for the seller.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        if not request.user.is_seller:
            return Response(
                {"detail": "You are not a seller."},
                status=status.HTTP_403_FORBIDDEN,
            )

        products = (
            DigitalProduct.objects
            .filter(seller=request.user)
            .exclude(status=DigitalProduct.Status.ARCHIVED)
            .order_by("-sales_count")
        )

        data = [
            {
                "id": str(p.id),
                "title": p.title,
                "slug": p.slug,
                "status": p.status,
                "views": p.view_count,
                "sales": p.sales_count,
                "downloads": p.download_count,
                "rating": str(p.average_rating),
                "reviews": p.review_count,
                "conversion_rate": (
                    round((p.sales_count / p.view_count) * 100, 2)
                    if p.view_count > 0 else 0
                ),
                "revenue": str(
                    OrderItem.objects.filter(
                        product=p,
                        order__status=Order.Status.COMPLETED,
                        is_refunded=False,
                    ).aggregate(total=Sum("seller_amount"))["total"]
                    or Decimal("0.00")
                ),
            }
            for p in products
        ]

        return Response(data)


class DownloadStatsView(generics.ListAPIView):
    """
    Download statistics for the seller's products.
    """

    serializer_class = DownloadStatSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return (
            DownloadStat.objects
            .filter(product__seller=self.request.user)
            .select_related("product")
            .order_by("-date")[:90]
        )
