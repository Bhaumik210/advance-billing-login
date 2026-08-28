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
        "forgot-password/",
        views.forgot_password,
        name="forgot_password"
    ),

    path(
        "distributor/profile/",
        views.distributor_profile,
        name="distributor_profile"
    ),

    path(
        "distributor/profile/edit/",
        views.edit_distributor_profile,
        name="edit_distributor_profile"
    ),

    path(
        "customers/",
        views.customer_list,
        name="customer_list"
    ),

    path(
        "customers/add/",
        views.add_customer,
        name="add_customer"
    ),

    path(
        "customers/<int:customer_id>/edit/",
        views.edit_customer,
        name="edit_customer"
    ),

    path(
        "customers/<int:customer_id>/delete/",
        views.delete_customer,
        name="delete_customer"
    ),

    path(
        "products/add/",
        views.add_product,
        name="add_product"
    ),

    path(
        "dashboard/",
        views.dashboard,
        name="dashboard"
    ),
]