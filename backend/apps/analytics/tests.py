"""
Tests for the analytics app: dashboard, sales data, reports, and services.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from apps.accounts.models import User, SellerProfile
from apps.orders.models import Order, OrderItem
from apps.products.models import DigitalProduct, Category, License
from .models import ProductView, DownloadStat, SalesReport
from .services import AnalyticsService


class AnalyticsModelTest(TestCase):
    """Test analytics model creation and constraints."""

    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@test.com",
            password="TestPass123!",
            username="testseller",
            role=User.Role.SELLER,
        )
        self.category = Category.objects.create(
            name="Templates", slug="templates"
        )
        self.product = DigitalProduct.objects.create(
            seller=self.seller,
            title="Test Product",
            slug="test-product",
            description="A test product.",
            category=self.category,
            status=DigitalProduct.Status.PUBLISHED,
        )

    def test_product_view_creation(self):
        view = ProductView.objects.create(
            product=self.product,
            ip_address="127.0.0.1",
            session_id="abc123",
        )
        self.assertEqual(str(view), f"View: Test Product at {view.viewed_at}")

    def test_download_stat_creation(self):
        today = timezone.now().date()
        stat = DownloadStat.objects.create(
            product=self.product,
            date=today,
            download_count=42,
            unique_downloaders=30,
        )
        self.assertIn("42 downloads", str(stat))

    def test_download_stat_unique_constraint(self):
        today = timezone.now().date()
        DownloadStat.objects.create(
            product=self.product, date=today, download_count=1
        )
        with self.assertRaises(Exception):
            DownloadStat.objects.create(
                product=self.product, date=today, download_count=2
            )

    def test_sales_report_creation(self):
        today = timezone.now().date()
        report = SalesReport.objects.create(
            report_type=SalesReport.ReportType.DAILY,
            report_date=today,
            total_orders=10,
            total_revenue=Decimal("500.00"),
            total_platform_fees=Decimal("75.00"),
            total_seller_earnings=Decimal("425.00"),
        )
        self.assertIn("daily", str(report))
        self.assertIn("Platform", str(report))

    def test_seller_sales_report(self):
        today = timezone.now().date()
        report = SalesReport.objects.create(
            seller=self.seller,
            report_type=SalesReport.ReportType.MONTHLY,
            report_date=today,
            total_orders=5,
            total_revenue=Decimal("200.00"),
        )
        self.assertIn(self.seller.email, str(report))


class DashboardViewTest(APITestCase):
    """Test the seller dashboard API endpoint."""

    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@test.com",
            password="TestPass123!",
            username="dashseller",
            role=User.Role.SELLER,
        )
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller,
            store_name="Test Store",
            store_slug="test-store",
        )
        self.buyer = User.objects.create_user(
            email="buyer@test.com",
            password="TestPass123!",
            username="dashbuyer",
            role=User.Role.BUYER,
        )
        self.client = APIClient()

    def test_dashboard_requires_auth(self):
        response = self.client.get("/api/v1/analytics/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dashboard_requires_seller_role(self):
        self.client.force_authenticate(user=self.buyer)
        response = self.client.get("/api/v1/analytics/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_returns_metrics(self):
        self.client.force_authenticate(user=self.seller)
        response = self.client.get("/api/v1/analytics/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertIn("total_revenue", data)
        self.assertIn("total_sales", data)
        self.assertIn("total_products", data)
        self.assertIn("revenue_chart", data)


class SalesDataViewTest(APITestCase):
    """Test the sales data API endpoint."""

    def setUp(self):
        self.seller = User.objects.create_user(
            email="salesseller@test.com",
            password="TestPass123!",
            username="salesseller",
            role=User.Role.SELLER,
        )
        SellerProfile.objects.create(
            user=self.seller,
            store_name="Sales Store",
            store_slug="sales-store",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.seller)

    def test_sales_data_default_period(self):
        response = self.client.get("/api/v1/analytics/sales/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["period"], "30d")
        self.assertIn("data", response.data)
        self.assertIn("totals", response.data)

    def test_sales_data_custom_period(self):
        response = self.client.get("/api/v1/analytics/sales/?period=7d&group_by=day")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["period"], "7d")

    def test_sales_data_weekly_grouping(self):
        response = self.client.get("/api/v1/analytics/sales/?period=90d&group_by=week")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["group_by"], "week")


class AnalyticsServiceTest(TestCase):
    """Test the AnalyticsService methods."""

    def setUp(self):
        self.seller = User.objects.create_user(
            email="svc_seller@test.com",
            password="TestPass123!",
            username="svcseller",
            role=User.Role.SELLER,
        )
        self.category = Category.objects.create(
            name="Themes", slug="themes"
        )
        self.product = DigitalProduct.objects.create(
            seller=self.seller,
            title="Analytics Test Product",
            slug="analytics-test-product",
            description="Test.",
            category=self.category,
            status=DigitalProduct.Status.PUBLISHED,
        )

    def test_track_product_view(self):
        factory = RequestFactory()
        request = factory.get("/products/analytics-test-product/")
        request.user = self.seller
        request.session = type("Session", (), {"session_key": "sess123"})()
        request.META["HTTP_USER_AGENT"] = "TestAgent"
        request.META["HTTP_REFERER"] = "https://google.com"

        view = AnalyticsService.track_product_view(self.product, request)
        self.assertIsNotNone(view)
        self.assertEqual(view.product, self.product)
        self.assertEqual(view.session_id, "sess123")

    def test_track_product_view_dedup(self):
        factory = RequestFactory()
        request = factory.get("/products/analytics-test-product/")
        request.user = self.seller
        request.session = type("Session", (), {"session_key": "dedup123"})()
        request.META["HTTP_USER_AGENT"] = "TestAgent"
        request.META["HTTP_REFERER"] = ""

        view1 = AnalyticsService.track_product_view(self.product, request)
        view2 = AnalyticsService.track_product_view(self.product, request)
        self.assertIsNotNone(view1)
        self.assertIsNone(view2)

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_get_seller_dashboard(self):
        data = AnalyticsService.get_seller_dashboard(str(self.seller.id))
        self.assertIn("total_products", data)
        self.assertIn("total_revenue", data)
        self.assertEqual(data["total_products"], 1)

    def test_generate_sales_report(self):
        today = timezone.now().date()
        report = AnalyticsService.generate_sales_report(
            report_date=today, report_type="daily"
        )
        self.assertIsInstance(report, SalesReport)
        self.assertEqual(report.report_type, "daily")
        self.assertEqual(report.report_date, today)
