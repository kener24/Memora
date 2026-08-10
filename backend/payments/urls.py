from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ContractPaymentPreviewView, ContractPaymentsView, ContractSettlementView,
    PaymentOptionsView, PaymentViewSet,
)


router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = [
    path("payments/options/", PaymentOptionsView.as_view(), name="payment-options"),
    path("contracts/<int:contract_id>/payments/", ContractPaymentsView.as_view(), name="contract-payments"),
    path("contracts/<int:contract_id>/payments/preview/", ContractPaymentPreviewView.as_view(), name="payment-preview"),
    path("contracts/<int:contract_id>/settle/", ContractSettlementView.as_view(), name="contract-settlement"),
    path("", include(router.urls)),
]
