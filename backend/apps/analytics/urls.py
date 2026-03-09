"""
Analytics URL routing.
"""

from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("sales/", views.SalesDataView.as_view(), name="sales-data"),
    path("products/", views.ProductPerformanceView.as_view(), name="product-performance"),
    path("downloads/", views.DownloadStatsView.as_view(), name="download-stats"),
]
