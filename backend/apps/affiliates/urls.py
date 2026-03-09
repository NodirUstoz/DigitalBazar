"""
Affiliate URL routing.
"""

from django.urls import path
from . import views

app_name = "affiliates"

urlpatterns = [
    path(
        "programs/",
        views.AffiliateProgramListView.as_view(),
        name="program-list",
    ),
    path(
        "seller/programs/",
        views.SellerAffiliateProgramView.as_view(),
        name="seller-programs",
    ),
    path(
        "links/",
        views.GenerateAffiliateLinkView.as_view(),
        name="generate-link",
    ),
    path(
        "my-links/",
        views.AffiliateLinksListView.as_view(),
        name="my-links",
    ),
    path(
        "commissions/",
        views.CommissionListView.as_view(),
        name="commissions",
    ),
    path(
        "stats/",
        views.AffiliateStatsView.as_view(),
        name="stats",
    ),
    path(
        "track-click/",
        views.TrackAffiliateLinkClickView.as_view(),
        name="track-click",
    ),
]
