"""
Order views: checkout, order history, downloads, license management.
"""

import logging
from decimal import Decimal

from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.models import DigitalProduct, License, ProductFile
from apps.affiliates.models import AffiliateLink
from utils.license_generator import generate_license_key
from .models import Order, OrderItem, LicenseKey, Download
from .serializers import (
    OrderSerializer, OrderListSerializer, CheckoutSerializer,
    LicenseKeySerializer, DownloadSerializer,
)

logger = logging.getLogger(__name__)


class CheckoutView(APIView):
    """
    Create an order from cart items.
    Validates products and licenses, calculates totals,
    and returns order details for payment processing.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        items_data = serializer.validated_data["items"]
        affiliate_code = serializer.validated_data.get("affiliate_code", "")

        # Validate all items exist and are purchasable
        order_items = []
        subtotal = Decimal("0.00")

        for item_data in items_data:
            try:
                product = DigitalProduct.objects.get(
                    id=item_data["product_id"],
                    status=DigitalProduct.Status.PUBLISHED,
                )
            except DigitalProduct.DoesNotExist:
                return Response(
                    {"detail": f"Product {item_data['product_id']} not found or unavailable."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if product.seller == request.user:
                return Response(
                    {"detail": "You cannot purchase your own product."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                license_obj = License.objects.get(
                    id=item_data["license_id"],
                    product=product,
                    is_active=True,
                )
            except License.DoesNotExist:
                return Response(
                    {"detail": f"License not found for product {product.title}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check for duplicate purchase
            existing = OrderItem.objects.filter(
                order__buyer=request.user,
                product=product,
                license=license_obj,
                order__status=Order.Status.COMPLETED,
                is_refunded=False,
            ).exists()
            if existing:
                return Response(
                    {"detail": f"You already own '{product.title}' with this license."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order_items.append({
                "product": product,
                "license": license_obj,
                "price": license_obj.price,
            })
            subtotal += license_obj.price

        # Look up affiliate link
        affiliate_link_obj = None
        if affiliate_code:
            try:
                affiliate_link_obj = AffiliateLink.objects.get(
                    code=affiliate_code, is_active=True
                )
            except AffiliateLink.DoesNotExist:
                pass  # Silently ignore invalid affiliate codes

        # Create the order
        platform_fee_total = Decimal("0.00")
        order = Order.objects.create(
            buyer=request.user,
            subtotal=subtotal,
            total=subtotal,
            affiliate_link=affiliate_link_obj,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        for item in order_items:
            product = item["product"]
            seller = product.seller

            # Calculate commission
            try:
                commission_rate = seller.seller_profile.commission_rate
            except Exception:
                commission_rate = Decimal(str(settings.PLATFORM_COMMISSION))

            platform_fee = (item["price"] * commission_rate / Decimal("100")).quantize(
                Decimal("0.01")
            )
            seller_amount = item["price"] - platform_fee
            platform_fee_total += platform_fee

            OrderItem.objects.create(
                order=order,
                product=product,
                license=item["license"],
                seller=seller,
                product_title=product.title,
                license_name=item["license"].name,
                price=item["price"],
                seller_amount=seller_amount,
                platform_fee=platform_fee,
            )

        order.platform_fee = platform_fee_total
        order.save(update_fields=["platform_fee"])

        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class OrderListView(generics.ListAPIView):
    """List orders for the current user."""

    serializer_class = OrderListSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user)


class OrderDetailView(generics.RetrieveAPIView):
    """Get order details."""

    serializer_class = OrderSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = "id"

    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user).prefetch_related(
            "items", "items__license_key"
        )


class DownloadFileView(APIView):
    """
    Download a purchased product file.
    Validates license key, checks download limits, and serves the file.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, order_id, file_id):
        # Find the order and verify ownership
        try:
            order = Order.objects.get(
                id=order_id,
                buyer=request.user,
                status=Order.Status.COMPLETED,
            )
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found or not completed."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Find the file
        try:
            product_file = ProductFile.objects.get(id=file_id)
        except ProductFile.DoesNotExist:
            return Response(
                {"detail": "File not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check that the order contains this product
        order_item = order.items.filter(product=product_file.product).first()
        if not order_item:
            return Response(
                {"detail": "This file is not part of your order."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check license key validity
        try:
            license_key = order_item.license_key
        except LicenseKey.DoesNotExist:
            return Response(
                {"detail": "No license key found for this purchase."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not license_key.is_valid:
            return Response(
                {"detail": "License key is invalid or download limit exceeded."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Record the download
        Download.objects.create(
            license_key=license_key,
            buyer=request.user,
            product_file=product_file,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        # Increment download count
        license_key.download_count += 1
        license_key.save(update_fields=["download_count"])

        # Serve the file
        response = FileResponse(
            product_file.file.open("rb"),
            content_type="application/octet-stream",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{product_file.original_filename}"'
        )
        return response

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class UserLicenseKeyListView(generics.ListAPIView):
    """List all license keys owned by the current user."""

    serializer_class = LicenseKeySerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return (
            LicenseKey.objects
            .filter(buyer=self.request.user)
            .select_related("order_item")
        )


class ValidateLicenseKeyView(APIView):
    """
    Public API endpoint to validate a license key.
    Used by third-party software for activation checks.
    """

    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        key = request.data.get("key")
        if not key:
            return Response(
                {"detail": "License key is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            license_key = LicenseKey.objects.select_related(
                "order_item", "order_item__product", "order_item__license"
            ).get(key=key)
        except LicenseKey.DoesNotExist:
            return Response(
                {"valid": False, "detail": "License key not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            "valid": license_key.is_valid,
            "status": license_key.status,
            "product": license_key.order_item.product_title,
            "license_type": (
                license_key.order_item.license.license_type
                if license_key.order_item.license else "unknown"
            ),
            "downloads_remaining": license_key.downloads_remaining,
            "activated_at": license_key.activated_at,
            "expires_at": license_key.expires_at,
        })


class SellerOrderListView(generics.ListAPIView):
    """List orders containing the seller's products."""

    serializer_class = OrderListSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return (
            Order.objects
            .filter(items__seller=self.request.user)
            .distinct()
            .order_by("-created_at")
        )
