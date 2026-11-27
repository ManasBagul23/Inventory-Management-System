from django.contrib import admin
from django.urls import path

from stock import views

urlpatterns = [
    path("", views.index),
    path("admin/", admin.site.urls),
    path("assets/<str:name>", views.asset),
    path("api/session/", views.session),
    path("api/workspace/", views.workspace),
    path("api/products/", views.product),
    path("api/products/<int:identifier>/movement/", views.movement),
    path("api/quotations/", views.quotation),
    path("api/quotations/<int:identifier>/<str:action>/", views.quotation_action),
    path("api/notifications/<int:identifier>/read/", views.read_notification),
]
