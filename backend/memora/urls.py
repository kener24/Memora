from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("customers.urls")),
    path("api/plans/", include("plans.urls")),
    path("api/", include("contracts.urls")),
]

admin.site.site_header = "Administración de Memora"
admin.site.site_title = "Memora"
admin.site.index_title = "Configuración inicial"
