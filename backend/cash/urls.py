from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CashDashboardView, CashMovementExcelView, CashMovementViewSet, CashRegisterViewSet,
    CashSessionViewSet, CashOptionsView, SettlementReceptionViewSet,
)


router = DefaultRouter()
router.register("registers", CashRegisterViewSet, basename="cash-register")
router.register("sessions", CashSessionViewSet, basename="cash-session")
router.register("movements", CashMovementViewSet, basename="cash-movement")
router.register("settlement-receptions", SettlementReceptionViewSet, basename="cash-settlement-reception")

urlpatterns = [
    path("dashboard/", CashDashboardView.as_view(), name="cash-dashboard"),
    path("options/", CashOptionsView.as_view(), name="cash-options"),
    path("movements/export.xlsx", CashMovementExcelView.as_view(), name="cash-movements-excel"),
    path("", include(router.urls)),
]
