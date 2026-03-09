"""
Order URL routing.
"""

from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("", views.OrderListView.as_view(), name="order-list"),
    path("<uuid:id>/", views.OrderDetailView.as_view(), name="order-detail"),
    path(
        "<uuid:order_id>/download/<uuid:file_id>/",
        views.DownloadFileView.as_view(),
        name="download-file",
    ),
    path("licenses/", views.UserLicenseKeyListView.as_view(), name="license-list"),
    path(
        "licenses/validate/",
        views.ValidateLicenseKeyView.as_view(),
        name="validate-license",
    ),
    path(
        "seller/orders/",
        views.SellerOrderListView.as_view(),
        name="seller-orders",
    ),
]
