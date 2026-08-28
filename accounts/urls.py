from django.urls import path
from . import views


urlpatterns = [
    path(
        "login/admin/",
        views.admin_login,
        name="admin_login"
    ),

    path(
        "login/distributor/",
        views.distributor_login,
        name="distributor_login"
    ),

    path(
        "register/distributor/",
        views.distributor_register,
        name="distributor_register"
    ),

    path(
        "otp/generate/",
        views.generate_otp,
        name="generate_otp"
    ),

    path(
        "otp/verify/",
        views.verify_otp,
        name="verify_otp"
    ),

    path(
        "dashboard/",
        views.dashboard,
        name="dashboard"
    ),
]