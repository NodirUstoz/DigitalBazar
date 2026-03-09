"""
Account views: registration, login, profile management.
"""

from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import SellerProfile, BuyerProfile
from .serializers import (
    UserRegistrationSerializer,
    UserSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    SellerProfileSerializer,
    SellerProfileUpdateSerializer,
    BuyerProfileSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """Register a new user (buyer, seller, or affiliate)."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = (permissions.AllowAny,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """Obtain JWT token pair via email and password."""

    permission_classes = (permissions.AllowAny,)


class TokenRefreshAPIView(TokenRefreshView):
    """Refresh an access token using a valid refresh token."""

    permission_classes = (permissions.AllowAny,)


class LogoutView(APIView):
    """Blacklist the refresh token to log out."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"detail": "Refresh token is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"detail": "Successfully logged out."},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {"detail": "Invalid token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class CurrentUserView(APIView):
    """Get or update the current authenticated user."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        serializer = UserSerializer(request.user)
        data = serializer.data

        if request.user.is_seller:
            try:
                seller_profile = request.user.seller_profile
                data["seller_profile"] = SellerProfileSerializer(seller_profile).data
            except SellerProfile.DoesNotExist:
                data["seller_profile"] = None

        if request.user.is_buyer:
            try:
                buyer_profile = request.user.buyer_profile
                data["buyer_profile"] = BuyerProfileSerializer(buyer_profile).data
            except BuyerProfile.DoesNotExist:
                data["buyer_profile"] = None

        return Response(data)

    def put(self, request):
        serializer = UserUpdateSerializer(
            request.user, data=request.data, partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    """Change the current user password."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response(
            {"detail": "Password updated successfully."},
            status=status.HTTP_200_OK,
        )


class SellerProfileView(APIView):
    """Get or update the current seller profile."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        if not request.user.is_seller:
            return Response(
                {"detail": "You are not a seller."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            profile = request.user.seller_profile
        except SellerProfile.DoesNotExist:
            return Response(
                {"detail": "Seller profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(SellerProfileSerializer(profile).data)

    def put(self, request):
        if not request.user.is_seller:
            return Response(
                {"detail": "You are not a seller."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            profile = request.user.seller_profile
        except SellerProfile.DoesNotExist:
            return Response(
                {"detail": "Seller profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SellerProfileUpdateSerializer(
            profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SellerProfileSerializer(profile).data)


class SellerPublicProfileView(generics.RetrieveAPIView):
    """Public view of a seller's store profile."""

    queryset = SellerProfile.objects.filter(
        verification_status=SellerProfile.VerificationStatus.VERIFIED
    )
    serializer_class = SellerProfileSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = "store_slug"
    lookup_url_kwarg = "slug"
