from django.urls import path
from . import views

urlpatterns = [
    path("login/admin/", views.admin_login, name="admin_login"),
    path(
        "login/distributor/",
        views.distributor_login,
        name="distributor_login"
    ),
    path("dashboard/", views.dashboard, name="dashboard"),
]