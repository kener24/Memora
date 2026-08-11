from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AgingSummaryView, CollectionActionViewSet, CollectionOptionsView, ContractCollectionView,
    CustomerCollectionView, FollowUpAgendaView, PaymentPromiseViewSet, PortfolioExcelView,
    PortfolioListView, PortfolioPDFView, PortfolioSummaryView,
)


router = DefaultRouter()
router.register("collection-actions", CollectionActionViewSet, basename="collection-action")
router.register("payment-promises", PaymentPromiseViewSet, basename="payment-promise")

urlpatterns = [
    path("portfolio/", PortfolioListView.as_view(), name="portfolio-list"),
    path("portfolio/summary/", PortfolioSummaryView.as_view(), name="portfolio-summary"),
    path("portfolio/aging/", AgingSummaryView.as_view(), name="portfolio-aging"),
    path("portfolio/options/", CollectionOptionsView.as_view(), name="collection-options"),
    path("portfolio/export.xlsx", PortfolioExcelView.as_view(), name="portfolio-excel"),
    path("portfolio/export.pdf", PortfolioPDFView.as_view(), name="portfolio-pdf"),
    path("portfolio/contracts/<int:contract_id>/", ContractCollectionView.as_view(), name="contract-collection"),
    path("portfolio/customers/<int:customer_id>/", CustomerCollectionView.as_view(), name="customer-collection"),
    path("collection-follow-ups/", FollowUpAgendaView.as_view(), name="collection-follow-ups"),
    path("", include(router.urls)),
]

