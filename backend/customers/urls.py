from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BeneficiaryDetailView,
    BeneficiaryListCreateView,
    ContactDetailView,
    ContactListCreateView,
    CustomerViewSet,
)


router = DefaultRouter()
router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "customers/<int:customer_id>/beneficiaries/",
        BeneficiaryListCreateView.as_view(),
        name="beneficiary-list-create",
    ),
    path(
        "customers/<int:customer_id>/beneficiaries/<int:pk>/",
        BeneficiaryDetailView.as_view(),
        name="beneficiary-detail",
    ),
    path(
        "customers/<int:customer_id>/contacts/",
        ContactListCreateView.as_view(),
        name="contact-list-create",
    ),
    path(
        "customers/<int:customer_id>/contacts/<int:pk>/",
        ContactDetailView.as_view(),
        name="contact-detail",
    ),
]
