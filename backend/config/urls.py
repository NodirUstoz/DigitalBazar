"""
URL configuration for DigitalBazar project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/products/", include("apps.products.urls")),
    path("api/v1/orders/", include("apps.orders.urls")),
    path("api/v1/payments/", include("apps.payments.urls")),
    path("api/v1/affiliates/", include("apps.affiliates.urls")),
    path("api/v1/analytics/", include("apps.analytics.urls")),
    path("api/v1/reviews/", include("apps.reviews.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "DigitalBazar Administration"
admin.site.site_title = "DigitalBazar Admin"
admin.site.index_title = "Dashboard"
