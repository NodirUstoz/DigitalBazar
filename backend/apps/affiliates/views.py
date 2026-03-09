"""
Affiliate views: programs, links, commissions, statistics.
"""

from decimal import Decimal

from django.db.models import Sum, Count
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AffiliateProgram, AffiliateLink, Commission
from .serializers import (
    AffiliateProgramSerializer,
    AffiliateProgramCreateSerializer,
    AffiliateLinkSerializer,
    CommissionSerializer,
)


class AffiliateProgramListView(generics.ListAPIView):
    """List all active affiliate programs (public)."""

    serializer_class = AffiliateProgramSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        return (
            AffiliateProgram.objects
            .filter(is_active=True, product__status="published")
            .select_related("product", "seller")
        )


class SellerAffiliateProgramView(APIView):
    """Manage affiliate programs for the seller's products."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        """List seller's affiliate programs."""
        if not request.user.is_seller:
            return Response(
                {"detail": "You are not a seller."},
                status=status.HTTP_403_FORBIDDEN,
            )
        programs = AffiliateProgram.objects.filter(seller=request.user)
        serializer = AffiliateProgramSerializer(programs, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create a new affiliate program."""
        if not request.user.is_seller:
            return Response(
                {"detail": "You are not a seller."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AffiliateProgramCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = serializer.validated_data["product"]
        if product.seller != request.user:
            return Response(
                {"detail": "You can only create affiliate programs for your own products."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer.save(seller=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GenerateAffiliateLinkView(APIView):
    """Generate an affiliate link for a program."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        program_id = request.data.get("program_id")
        if not program_id:
            return Response(
                {"detail": "program_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            program = AffiliateProgram.objects.get(
                id=program_id, is_active=True
            )
        except AffiliateProgram.DoesNotExist:
            return Response(
                {"detail": "Affiliate program not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Cannot be an affiliate for your own product
        if program.seller == request.user:
            return Response(
                {"detail": "You cannot be an affiliate for your own product."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for existing link
        existing = AffiliateLink.objects.filter(
            program=program, affiliate=request.user
        ).first()
        if existing:
            return Response(
                AffiliateLinkSerializer(existing).data,
                status=status.HTTP_200_OK,
            )

        link = AffiliateLink.objects.create(
            program=program,
            affiliate=request.user,
        )

        # Update program stats
        AffiliateProgram.objects.filter(pk=program.pk).update(
            total_affiliates=program.total_affiliates + 1
        )

        return Response(
            AffiliateLinkSerializer(link).data,
            status=status.HTTP_201_CREATED,
        )


class AffiliateLinksListView(generics.ListAPIView):
    """List all affiliate links for the authenticated user."""

    serializer_class = AffiliateLinkSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return (
            AffiliateLink.objects
            .filter(affiliate=self.request.user)
            .select_related("program", "program__product")
        )


class CommissionListView(generics.ListAPIView):
    """List commission history for the authenticated affiliate."""

    serializer_class = CommissionSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return (
            Commission.objects
            .filter(affiliate=self.request.user)
            .select_related("affiliate_link__program__product", "order")
        )


class AffiliateStatsView(APIView):
    """Get affiliate statistics for the authenticated user."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        links = AffiliateLink.objects.filter(affiliate=request.user)
        commissions = Commission.objects.filter(affiliate=request.user)

        stats = {
            "total_links": links.count(),
            "total_clicks": links.aggregate(
                total=Sum("click_count")
            )["total"] or 0,
            "total_conversions": links.aggregate(
                total=Sum("conversion_count")
            )["total"] or 0,
            "total_earned": str(
                commissions.filter(
                    status__in=[Commission.Status.APPROVED, Commission.Status.PAID]
                ).aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
            ),
            "pending_earnings": str(
                commissions.filter(
                    status=Commission.Status.PENDING
                ).aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
            ),
            "total_paid": str(
                commissions.filter(
                    status=Commission.Status.PAID
                ).aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
            ),
        }

        return Response(stats)


class TrackAffiliateLinkClickView(APIView):
    """Track a click on an affiliate link (called from frontend)."""

    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        code = request.data.get("code")
        if not code:
            return Response(
                {"detail": "Affiliate code is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            link = AffiliateLink.objects.get(code=code, is_active=True)
        except AffiliateLink.DoesNotExist:
            return Response(
                {"detail": "Invalid affiliate code."},
                status=status.HTTP_404_NOT_FOUND,
            )

        link.click_count += 1
        link.save(update_fields=["click_count"])

        return Response({
            "product_slug": link.program.product.slug,
            "cookie_duration": link.program.cookie_duration_days,
        })
