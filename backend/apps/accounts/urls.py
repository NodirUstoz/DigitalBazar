"""
Account URL routing.
"""

from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("token/refresh/", views.TokenRefreshAPIView.as_view(), name="token-refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.CurrentUserView.as_view(), name="current-user"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change-password"),
    path("seller-profile/", views.SellerProfileView.as_view(), name="seller-profile"),
    path(
        "sellers/<slug:slug>/",
        views.SellerPublicProfileView.as_view(),
        name="seller-public-profile",
    ),
]
