"""Compatibility exports for the accounts view modules."""

from .auth_views import (
    admin_register,
    admin_register_api,
    admin_login,
    distributor_login,
    distributor_register,
    generate_otp,
    verify_otp,
    forgot_password,
    _get_application_admin,
    admin_generate_otp,
    admin_forgot_password,
    distributor_profile,
    edit_distributor_profile,
)

from .customer_views import (
    customer_register_api,
    add_customer,
    customer_list,
    edit_customer,
    delete_customer,
)

from .inventory_views import (
    add_product,
    product_list,
    delete_product,
    edit_product,
)

from .billing_views import (
    create_invoice,
    invoice_list,
    invoice_detail,
    download_invoice_pdf,
)

from .payment_views import (
    invoice_payments,
)

from .dashboard_views import (
    dashboard,
    admin_reports,
    qr_scanner,
)
