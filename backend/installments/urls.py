from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ContractScheduleView, GenerateScheduleView, InstallmentOptionsView, InstallmentSummaryView,
    InstallmentViewSet, PaymentPlanPDFView, PreviewScheduleView, ReprogramScheduleView,
)


router = DefaultRouter()
router.register("installments", InstallmentViewSet, basename="installment")

urlpatterns = [
    path("installments/options/", InstallmentOptionsView.as_view(), name="installment-options"),
    path("installments/summary/", InstallmentSummaryView.as_view(), name="installment-summary"),
    path(
        "contracts/<int:contract_id>/installment-schedule/",
        ContractScheduleView.as_view(), name="contract-installment-schedule",
    ),
    path(
        "contracts/<int:contract_id>/installment-schedule/generate/",
        GenerateScheduleView.as_view(), name="generate-installment-schedule",
    ),
    path(
        "contracts/<int:contract_id>/installment-schedule/preview/",
        PreviewScheduleView.as_view(), name="preview-installment-schedule",
    ),
    path(
        "contracts/<int:contract_id>/installment-schedule/reprogram/",
        ReprogramScheduleView.as_view(), name="reprogram-installment-schedule",
    ),
    path(
        "contracts/<int:contract_id>/installment-schedule/pdf/",
        PaymentPlanPDFView.as_view(), name="installment-schedule-pdf",
    ),
    path("", include(router.urls)),
]
