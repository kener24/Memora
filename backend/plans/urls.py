from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FuneralPlanViewSet, ServiceViewSet


router = DefaultRouter()
router.register("services", ServiceViewSet, basename="plan-service")
router.register("", FuneralPlanViewSet, basename="funeral-plan")

urlpatterns = [path("", include(router.urls))]
