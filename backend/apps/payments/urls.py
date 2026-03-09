"""
Payment URL routing.
"""

from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path(
        "create-intent/",
        views.CreatePaymentIntentView.as_view(),
        name="create-payment-intent",
    ),
    path("webhook/", views.stripe_webhook, name="stripe-webhook"),
    path(
        "refund-request/",
        views.RefundRequestView.as_view(),
        name="refund-request",
    ),
    path(
        "payouts/",
        views.SellerPayoutListView.as_view(),
        name="seller-payouts",
    ),
]
