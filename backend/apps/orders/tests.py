"""
Tests for the orders app: checkout, downloads, license validation, and services.
"""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from rest_framework import status as http_status

from apps.accounts.models import User, SellerProfile, BuyerProfile
from apps.products.models import Category, DigitalProduct, License, ProductFile
from .models import Order, OrderItem, LicenseKey, Download
from .services import OrderService


class OrderModelTest(TestCase):
    """Test order model creation and properties."""

    def setUp(self):
        self.buyer = User.objects.create_user(
            email="ordbuyer@test.com",
            password="TestPass123!",
            username="ordbuyer",
            role=User.Role.BUYER,
        )

    def test_order_number_auto_generated(self):
        order = Order.objects.create(
            buyer=self.buyer,
            subtotal=Decimal("25.00"),
            total=Decimal("25.00"),
        )
        self.assertTrue(order.order_number.startswith("DB-"))
        self.assertEqual(len(order.order_number), 11)

    def test_order_str(self):
        order = Order.objects.create(
            buyer=self.buyer,
            subtotal=Decimal("10.00"),
            total=Decimal("10.00"),
        )
        self.assertIn("ordbuyer@test.com", str(order))

    def test_order_item_count(self):
        order = Order.objects.create(
            buyer=self.buyer,
            subtotal=Decimal("50.00"),
            total=Decimal("50.00"),
        )
        self.assertEqual(order.item_count, 0)


class LicenseKeyModelTest(TestCase):
    """Test license key validity checks."""

    def setUp(self):
        self.buyer = User.objects.create_user(
            email="licbuyer@test.com",
            password="TestPass123!",
            username="licbuyer",
            role=User.Role.BUYER,
        )
        self.seller = User.objects.create_user(
            email="licseller@test.com",
            password="TestPass123!",
            username="licseller",
            role=User.Role.SELLER,
        )
        self.category = Category.objects.create(name="Fonts", slug="fonts")
        self.product = DigitalProduct.objects.create(
            seller=self.seller,
            title="Test Font",
            slug="test-font",
            description="Test.",
            category=self.category,
            status=DigitalProduct.Status.PUBLISHED,
        )
        self.license = License.objects.create(
            product=self.product,
            license_type=License.LicenseType.PERSONAL,
            name="Personal",
            price=Decimal("15.00"),
            max_downloads=3,
        )
        self.order = Order.objects.create(
            buyer=self.buyer,
            subtotal=Decimal("15.00"),
            total=Decimal("15.00"),
            status=Order.Status.COMPLETED,
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            license=self.license,
            seller=self.seller,
            product_title="Test Font",
            license_name="Personal",
            price=Decimal("15.00"),
            seller_amount=Decimal("12.75"),
            platform_fee=Decimal("2.25"),
        )

    def test_license_key_is_valid(self):
        key = LicenseKey.objects.create(
            order_item=self.order_item,
            buyer=self.buyer,
            key="DB-TEST-KEY1-ABCD-EFGH",
            max_downloads=3,
            download_count=0,
        )
        self.assertTrue(key.is_valid)

    def test_license_key_downloads_exhausted(self):
        key = LicenseKey.objects.create(
            order_item=self.order_item,
            buyer=self.buyer,
            key="DB-TEST-KEY2-ABCD-EFGH",
            max_downloads=3,
            download_count=3,
        )
        self.assertFalse(key.is_valid)
        self.assertEqual(key.downloads_remaining, 0)

    def test_license_key_revoked(self):
        key = LicenseKey.objects.create(
            order_item=self.order_item,
            buyer=self.buyer,
            key="DB-TEST-KEY3-ABCD-EFGH",
            max_downloads=3,
            status=LicenseKey.Status.REVOKED,
        )
        self.assertFalse(key.is_valid)


class CheckoutViewTest(APITestCase):
    """Test the checkout API endpoint."""

    def setUp(self):
        self.buyer = User.objects.create_user(
            email="chkbuyer@test.com",
            password="TestPass123!",
            username="chkbuyer",
            role=User.Role.BUYER,
        )
        BuyerProfile.objects.create(user=self.buyer)
        self.seller = User.objects.create_user(
            email="chkseller@test.com",
            password="TestPass123!",
            username="chkseller",
            role=User.Role.SELLER,
        )
        SellerProfile.objects.create(
            user=self.seller,
            store_name="Checkout Store",
            store_slug="checkout-store",
        )
        self.category = Category.objects.create(name="Software", slug="software")
        self.product = DigitalProduct.objects.create(
            seller=self.seller,
            title="Checkout Product",
            slug="checkout-product",
            description="Test product for checkout.",
            category=self.category,
            status=DigitalProduct.Status.PUBLISHED,
        )
        self.license = License.objects.create(
            product=self.product,
            license_type=License.LicenseType.PERSONAL,
            name="Personal",
            price=Decimal("29.99"),
            max_downloads=5,
        )
        ProductFile.objects.create(
            product=self.product,
            file="test.zip",
            original_filename="test.zip",
            file_size=1024,
            is_main=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.buyer)

    def test_checkout_success(self):
        response = self.client.post(
            "/api/v1/orders/checkout/",
            {
                "items": [
                    {
                        "product_id": str(self.product.id),
                        "license_id": str(self.license.id),
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertIn("order_number", response.data)
        self.assertEqual(response.data["total"], "29.99")

    def test_checkout_requires_auth(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"items": [{"product_id": str(self.product.id), "license_id": str(self.license.id)}]},
            format="json",
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_cannot_buy_own_product(self):
        self.client.force_authenticate(user=self.seller)
        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"items": [{"product_id": str(self.product.id), "license_id": str(self.license.id)}]},
            format="json",
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_checkout_empty_cart(self):
        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"items": []},
            format="json",
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)


class LicenseValidationViewTest(APITestCase):
    """Test the license key validation endpoint."""

    def setUp(self):
        self.buyer = User.objects.create_user(
            email="valbuyer@test.com",
            password="TestPass123!",
            username="valbuyer",
            role=User.Role.BUYER,
        )
        self.seller = User.objects.create_user(
            email="valseller@test.com",
            password="TestPass123!",
            username="valseller",
            role=User.Role.SELLER,
        )
        self.category = Category.objects.create(name="Plugins", slug="plugins")
        self.product = DigitalProduct.objects.create(
            seller=self.seller,
            title="Validation Product",
            slug="validation-product",
            description="Test.",
            category=self.category,
            status=DigitalProduct.Status.PUBLISHED,
        )
        self.license = License.objects.create(
            product=self.product,
            name="Standard",
            price=Decimal("10.00"),
            max_downloads=2,
        )
        self.order = Order.objects.create(
            buyer=self.buyer,
            subtotal=Decimal("10.00"),
            total=Decimal("10.00"),
            status=Order.Status.COMPLETED,
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            license=self.license,
            seller=self.seller,
            product_title="Validation Product",
            license_name="Standard",
            price=Decimal("10.00"),
            seller_amount=Decimal("8.50"),
            platform_fee=Decimal("1.50"),
        )
        self.license_key = LicenseKey.objects.create(
            order_item=self.order_item,
            buyer=self.buyer,
            key="DB-VALID-TESTK-ABCDE-FGHIJ",
            max_downloads=2,
        )
        self.client = APIClient()

    def test_validate_valid_key(self):
        response = self.client.post(
            "/api/v1/orders/licenses/validate/",
            {"key": "DB-VALID-TESTK-ABCDE-FGHIJ"},
            format="json",
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["product"], "Validation Product")

    def test_validate_nonexistent_key(self):
        response = self.client.post(
            "/api/v1/orders/licenses/validate/",
            {"key": "DB-NONEXISTENT-KEY"},
            format="json",
        )
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_validate_missing_key(self):
        response = self.client.post(
            "/api/v1/orders/licenses/validate/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
