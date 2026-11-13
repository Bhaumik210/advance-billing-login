from django.urls import path
from . import views

urlpatterns = [
    path("register/admin/", views.admin_register, name="admin_register"),
    path("api/register/admin/", views.admin_register_api, name="admin_register_api"),
    path("login/admin/", views.admin_login, name="admin_login"),
    path("admin-password/otp/", views.admin_generate_otp, name="admin_generate_otp"),
    path("admin-password/", views.admin_forgot_password, name="admin_forgot_password"),
    path("login/distributor/", views.distributor_login, name="distributor_login"),
    path("register/distributor/", views.distributor_register, name="distributor_register"),
    path("otp/generate/", views.generate_otp, name="generate_otp"),
    path("otp/verify/", views.verify_otp, name="verify_otp"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("distributor/profile/", views.distributor_profile, name="distributor_profile"),
    path("distributor/profile/edit/", views.edit_distributor_profile, name="edit_distributor_profile"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/add/", views.add_customer, name="add_customer"),
    path("customers/<int:customer_id>/edit/", views.edit_customer, name="edit_customer"),
    path("customers/<int:customer_id>/delete/", views.delete_customer, name="delete_customer"),
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.add_product, name="add_product"),
    path("products/<int:product_id>/edit/", views.edit_product, name="edit_product"),
    path("products/<int:product_id>/delete/", views.delete_product, name="delete_product"),
    path("invoices/create/", views.create_invoice, name="create_invoice"),
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/<int:invoice_id>/pdf/", views.download_invoice_pdf, name="download_invoice_pdf"),
    path("dashboard/", views.dashboard, name="dashboard"),
]
