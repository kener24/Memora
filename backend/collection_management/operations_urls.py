from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .operations_views import (
    AssignmentViewSet, CollectorPortfolioExcelView, CollectorViewSet, OperationsOptionsView, OwnCollectorMetricsView,
    OwnCollectorPortfolioView, OwnCollectorRoutesView, OwnCollectorTodayView, RouteViewSet,
    RouteVisitView, SettlementPDFView, SettlementsExcelView, SettlementViewSet, ProductivityExcelView,
    WorkSessionViewSet, ZoneViewSet,
)


router = DefaultRouter()
router.register("collectors", CollectorViewSet, basename="collector")
router.register("collection-assignments", AssignmentViewSet, basename="collection-assignment")
router.register("collection-zones", ZoneViewSet, basename="collection-zone")
router.register("collection-routes", RouteViewSet, basename="collection-route")
router.register("collector-work-sessions", WorkSessionViewSet, basename="collector-work-session")
router.register("collector-settlements", SettlementViewSet, basename="collector-settlement")

urlpatterns = [
    path("collector/portfolio/", OwnCollectorPortfolioView.as_view(), name="collector-own-portfolio"),
    path("collector/today/", OwnCollectorTodayView.as_view(), name="collector-today"),
    path("collector/metrics/", OwnCollectorMetricsView.as_view(), name="collector-own-metrics"),
    path("collector/routes/", OwnCollectorRoutesView.as_view(), name="collector-own-routes"),
    path("collector/route-stops/<int:stop_id>/visit/", RouteVisitView.as_view(), name="collector-route-visit"),
    path("collection-operations/options/", OperationsOptionsView.as_view(), name="collection-operations-options"),
    path("collectors/<int:collector_id>/portfolio/export.xlsx", CollectorPortfolioExcelView.as_view(), name="collector-portfolio-excel"),
    path("collectors/productivity/export.xlsx", ProductivityExcelView.as_view(), name="collector-productivity-excel"),
    path("collector-settlements/export.xlsx", SettlementsExcelView.as_view(), name="collector-settlements-excel"),
    path("collector-settlements/<int:settlement_id>/pdf/", SettlementPDFView.as_view(), name="collector-settlement-pdf"),
    path("", include(router.urls)),
]
