from PIL import Image
import random
import re

from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4

from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
)

from django.contrib.auth import (
    authenticate,
    login,
)

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages

from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache

from django.utils import timezone
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Q

from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator

from .models import (
    OTPVerification,
    DistributorProfile,
    Customer,
    Product,
    Invoice,
    InvoiceItem,
)


@never_cache
@ensure_csrf_cookie
def admin_login(request):

    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(
                request,
                user
            )

            return redirect(
                "dashboard"
            )

        return render(
            request,
            "accounts/admin_login.html",
            {
                "error": "Invalid username or password"
            }
        )

    return render(
        request,
        "accounts/admin_login.html"
    )


@never_cache
@ensure_csrf_cookie
def distributor_login(request):

    if request.method == "POST":

        login_value = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        username = login_value

        try:

            user_by_email = User.objects.get(
                email__iexact=login_value
            )

            username = user_by_email.username

        except User.DoesNotExist:
            pass

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(
                request,
                user
            )

            return redirect(
                "distributor_profile"
            )

        return render(
            request,
            "accounts/distributor_login.html",
            {
                "error": "Invalid username or password"
            }
        )

    return render(
        request,
        "accounts/distributor_login.html"
    )


def distributor_register(request):

    error = None

    form_data = {
        "name": "",
        "email": "",
        "phone": ""
    }

    if request.method == "POST":

        full_name = request.POST.get(
            "name",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip().lower()

        phone = request.POST.get(
            "phone",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        form_data = {
            "name": full_name,
            "email": email,
            "phone": phone
        }

        if not full_name:

            error = "Full name is required."

        elif len(full_name) < 2:

            error = (
                "Full name must contain "
                "at least 2 characters."
            )

        elif not re.fullmatch(
            r"[A-Za-z ]+",
            full_name
        ):

            error = (
                "Full name should contain "
                "only letters and spaces."
            )

        elif not email:

            error = (
                "Email address is required."
            )

        else:

            try:

                validate_email(email)

            except ValidationError:

                error = (
                    "Enter a valid email address."
                )

        if error is None:

            if not phone:

                error = (
                    "Phone number is required."
                )

            elif not phone.isdigit():

                error = (
                    "Phone number should contain "
                    "only digits."
                )

            elif len(phone) != 10:

                error = (
                    "Phone number must contain "
                    "exactly 10 digits."
                )

        if error is None:

            if not password:

                error = (
                    "Password is required."
                )

            elif len(password) < 8:

                error = (
                    "Password must be at least "
                    "8 characters long."
                )

            elif not re.search(
                r"[A-Z]",
                password
            ):

                error = (
                    "Password must contain "
                    "at least one uppercase letter."
                )

            elif not re.search(
                r"[a-z]",
                password
            ):

                error = (
                    "Password must contain "
                    "at least one lowercase letter."
                )

            elif not re.search(
                r"[0-9]",
                password
            ):

                error = (
                    "Password must contain "
                    "at least one number."
                )

        if error is None:

            if User.objects.filter(
                username=email
            ).exists():

                error = (
                    "This email is already registered."
                )

            elif User.objects.filter(
                email=email
            ).exists():

                error = (
                    "This email is already registered."
                )

        if error is None:

            name_parts = full_name.split(
                " ",
                1
            )

            first_name = name_parts[0]

            if len(name_parts) > 1:
                last_name = name_parts[1]
            else:
                last_name = ""

            with transaction.atomic():

                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )

                DistributorProfile.objects.create(
                    user=user,
                    phone=phone
                )

            messages.success(
                request,
                "Registration successful. "
                "Please login to continue."
            )

            return redirect(
                "distributor_login"
            )

    return render(
        request,
        "accounts/distributor_register.html",
        {
            "error": error,
            "form_data": form_data
        }
    )


def generate_otp(request):

    message = None

    if request.method == "POST":

        email = request.POST.get(
            "email",
            ""
        ).strip()

        if email:

            expiry_time = (
                timezone.now()
                - timedelta(minutes=5)
            )

            OTPVerification.objects.filter(
                created_at__lt=expiry_time
            ).delete()

            OTPVerification.objects.filter(
                email=email
            ).delete()

            otp_code = str(
                random.randint(
                    100000,
                    999999
                )
            )

            OTPVerification.objects.create(
                email=email,
                otp_code=otp_code
            )

            request.session[
                "otp_email"
            ] = email

            print(
                f"OTP for {email}: {otp_code}"
            )

            message = (
                "OTP generated successfully."
            )

    return render(
        request,
        "accounts/otp_generate.html",
        {
            "message": message
        }
    )


def verify_otp(request):

    message = None
    error = None

    if request.method == "POST":

        otp_code = request.POST.get(
            "otp",
            ""
        ).strip()

        email = request.session.get(
            "otp_email"
        )

        if not email:

            error = (
                "Please generate an OTP first."
            )

        else:

            otp_record = (
                OTPVerification.objects
                .filter(email=email)
                .order_by("-created_at")
                .first()
            )

            if otp_record is None:

                error = (
                    "OTP not found. "
                    "Please generate a new OTP."
                )

            elif otp_record.is_expired():

                otp_record.delete()

                error = (
                    "OTP has expired. "
                    "Please generate a new OTP."
                )

            elif otp_record.otp_code == otp_code:

                otp_record.delete()

                request.session.pop(
                    "otp_email",
                    None
                )

                message = (
                    "OTP verified successfully."
                )

            else:

                error = (
                    "Invalid OTP."
                )

    return render(
        request,
        "accounts/otp_verify.html",
        {
            "message": message,
            "error": error
        }
    )
def forgot_password(request):

    return render(
        request,
        "accounts/forgot_password.html"
    )


@login_required(
    login_url="distributor_login"
)
def distributor_profile(request):
    # Fetch the complete profile so business details and logo
    # are available to distributor_profile.html.
    profile, created = DistributorProfile.objects.get_or_create(
        user=request.user,
        defaults={"phone": ""}
    )

    phone = profile.phone or "Not added"

    return render(
        request,
        "accounts/distributor_profile.html",
        {
            "profile": profile,
            "phone": phone,
        }
    )


@login_required(
    login_url="distributor_login"
)
def edit_distributor_profile(request):
    user = request.user

    profile, created = DistributorProfile.objects.get_or_create(
        user=user,
        defaults={"phone": ""}
    )

    error = None
    form_data = {
        "name": user.get_full_name(),
        "email": user.email,
        "phone": profile.phone or "",
        "business_name": profile.business_name or "",
        "business_address": profile.business_address or "",
        "gstin": profile.gstin or "",
    }

    if request.method == "POST":
        full_name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        business_name = request.POST.get("business_name", "").strip()
        business_address = request.POST.get("business_address", "").strip()
        gstin = request.POST.get("gstin", "").strip().upper()
        logo_file = request.FILES.get("logo")

        form_data = {
            "name": full_name,
            "email": email,
            "phone": phone,
            "business_name": business_name,
            "business_address": business_address,
            "gstin": gstin,
        }

        # Validate personal information.
        if not full_name:
            error = "Full name is required."
        elif len(full_name) < 2:
            error = "Full name must contain at least 2 characters."
        elif not re.fullmatch(r"[A-Za-z ]+", full_name):
            error = "Full name should contain only letters and spaces."
        elif not email:
            error = "Email address is required."
        else:
            try:
                validate_email(email)
            except ValidationError:
                error = "Enter a valid email address."

        if error is None:
            duplicate_email = (
                User.objects
                .filter(email__iexact=email)
                .exclude(id=user.id)
                .exists()
            )
            if duplicate_email:
                error = "This email is already used by another account."

        if error is None:
            if not phone:
                error = "Phone number is required."
            elif not phone.isdigit():
                error = "Phone number should contain only digits."
            elif len(phone) != 10:
                error = "Phone number must contain exactly 10 digits."

        # Validate optional business information.
        if error is None and len(business_name) > 150:
            error = "Business name cannot exceed 150 characters."

        if error is None and gstin:
            gstin_pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
            if not re.fullmatch(gstin_pattern, gstin):
                error = "Enter a valid 15-character GSTIN, or leave it blank."

        # Validate uploaded logo, if a new file was selected.
        if error is None and logo_file:
            if logo_file.size > 2 * 1024 * 1024:
                error = "Company logo must be 2 MB or smaller."
            else:
                try:
                    logo_image = Image.open(logo_file)
                    image_format = logo_image.format
                    logo_image.verify()

                    if image_format not in {"JPEG", "PNG", "WEBP"}:
                        error = "Logo must be a JPG, JPEG, PNG, or WEBP image."
                    else:
                        logo_file.seek(0)
                except (OSError, ValueError):
                    error = "Please upload a valid image file."

        if error is None:
            name_parts = full_name.split(" ", 1)
            user.first_name = name_parts[0]
            user.last_name = name_parts[1] if len(name_parts) > 1 else ""
            user.email = email

            profile.phone = phone
            profile.business_name = business_name
            profile.business_address = business_address
            profile.gstin = gstin

            # Keep the existing logo when no new logo is uploaded.
            if logo_file:
                profile.logo = logo_file

            with transaction.atomic():
                user.save()
                profile.save()

            messages.success(request, "Profile updated successfully.")
            return redirect("distributor_profile")

    return render(
        request,
        "accounts/edit_distributor_profile.html",
        {
            "error": error,
            "profile": profile,
            "form_data": form_data,
        }
    )

def add_customer(request):

    error = None
    success = None

    form_data = {
        "name": "",
        "email": "",
        "phone": "",
        "address": ""
    }

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip()

        phone = request.POST.get(
            "phone",
            ""
        ).strip()

        address = request.POST.get(
            "address",
            ""
        ).strip()

        form_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "address": address
        }

        if not name:

            error = (
                "Customer name is required."
            )

        elif len(name) < 2:

            error = (
                "Customer name must contain "
                "at least 2 characters."
            )

        elif not re.fullmatch(
            r"[A-Za-z ]+",
            name
        ):

            error = (
                "Customer name should contain "
                "only letters and spaces."
            )

        elif not email:

            error = (
                "Email address is required."
            )

        else:

            try:

                validate_email(email)

            except ValidationError:

                error = (
                    "Enter a valid email address."
                )

        if error is None:

            if not phone:

                error = (
                    "Phone number is required."
                )

            elif not phone.isdigit():

                error = (
                    "Phone number should contain "
                    "only digits."
                )

            elif len(phone) != 10:

                error = (
                    "Phone number must contain "
                    "exactly 10 digits."
                )

        if error is None:

            if not address:

                error = (
                    "Address is required."
                )

            elif len(address) < 5:

                error = (
                    "Please enter a valid address."
                )

        if error is None:

            success = (
                "Customer added successfully."
            )

            form_data = {
                "name": "",
                "email": "",
                "phone": "",
                "address": ""
            }

    return render(
        request,
        "accounts/add_customer.html",
        {
            "error": error,
            "success": success,
            "form_data": form_data
        }
    )


@login_required(
    login_url="distributor_login"
)
def customer_list(request):

    search_query = request.GET.get(
        "search",
        ""
    ).strip()

    customers = Customer.objects.all()

    if search_query:

        customers = customers.filter(
            Q(name__icontains=search_query)
            |
            Q(email__icontains=search_query)
            |
            Q(phone__icontains=search_query)
            |
            Q(address__icontains=search_query)
        )

    customers = customers.order_by(
        "-created_at"
    )

    return render(
        request,
        "accounts/customer_list.html",
        {
            "customers": customers,
            "search_query": search_query
        }
    )


@login_required(
    login_url="distributor_login"
)
def edit_customer(
    request,
    customer_id
):

    customer = get_object_or_404(
        Customer,
        id=customer_id
    )

    error = None

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip().lower()

        phone = request.POST.get(
            "phone",
            ""
        ).strip()

        address = request.POST.get(
            "address",
            ""
        ).strip()

        if not name:

            error = (
                "Customer name is required."
            )

        elif len(name) < 2:

            error = (
                "Customer name must contain "
                "at least 2 characters."
            )

        elif not re.fullmatch(
            r"[A-Za-z ]+",
            name
        ):

            error = (
                "Customer name should contain "
                "only letters and spaces."
            )

        elif not email:

            error = (
                "Email address is required."
            )

        else:

            try:

                validate_email(email)

            except ValidationError:

                error = (
                    "Enter a valid email address."
                )

        if error is None:

            duplicate_email = (
                Customer.objects
                .filter(
                    email__iexact=email
                )
                .exclude(
                    id=customer.id
                )
                .exists()
            )

            if duplicate_email:

                error = (
                    "Another customer already uses "
                    "this email address."
                )

        if error is None:

            if not phone:

                error = (
                    "Phone number is required."
                )

            elif not phone.isdigit():

                error = (
                    "Phone number should "
                    "contain only digits."
                )

            elif len(phone) != 10:

                error = (
                    "Phone number must contain "
                    "exactly 10 digits."
                )

        if error is None:

            if not address:

                error = (
                    "Address is required."
                )

            elif len(address) < 5:

                error = (
                    "Please enter a valid address."
                )

        if error is None:

            customer.name = name
            customer.email = email
            customer.phone = phone
            customer.address = address

            customer.save()

            messages.success(
                request,
                "Customer updated successfully."
            )

            return redirect(
                "customer_list"
            )

    return render(
        request,
        "accounts/edit_customer.html",
        {
            "customer": customer,
            "error": error
        }
    )
@login_required(
    login_url="distributor_login"
)
def delete_customer(
    request,
    customer_id
):

    customer = get_object_or_404(
        Customer,
        id=customer_id
    )

    if request.method == "POST":

        customer_name = customer.name

        customer.delete()

        messages.success(
            request,
            f"{customer_name} deleted successfully."
        )

    return redirect(
        "customer_list"
    )


@login_required(
    login_url="distributor_login"
)
def add_product(request):

    error = None

    form_data = {
        "name": "",
        "category": "",
        "price": "",
        "stock": "",
        "gst_rate": "",
        "description": ""
    }

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        category = request.POST.get(
            "category",
            ""
        ).strip()

        price_value = request.POST.get(
            "price",
            ""
        ).strip()

        stock_value = request.POST.get(
            "stock",
            ""
        ).strip()

        gst_value = request.POST.get(
            "gst_rate",
            ""
        ).strip()

        description = request.POST.get(
            "description",
            ""
        ).strip()

        form_data = {
            "name": name,
            "category": category,
            "price": price_value,
            "stock": stock_value,
            "gst_rate": gst_value,
            "description": description
        }

        price = None
        stock = None
        gst_rate = None

        if not name:

            error = (
                "Product name is required."
            )

        elif len(name) < 2:

            error = (
                "Product name must contain "
                "at least 2 characters."
            )

        elif not category:

            error = (
                "Category is required."
            )

        if error is None:

            if not price_value:

                error = (
                    "Price is required."
                )

            else:

                try:

                    price = Decimal(
                        price_value
                    )

                    if price <= 0:

                        error = (
                            "Price must be greater than 0."
                        )

                except InvalidOperation:

                    error = (
                        "Enter a valid price."
                    )

        if error is None:

            if stock_value == "":

                error = (
                    "Stock is required."
                )

            else:

                try:

                    stock = int(
                        stock_value
                    )

                    if stock < 0:

                        error = (
                            "Stock cannot be negative."
                        )

                except ValueError:

                    error = (
                        "Stock must be a whole number."
                    )

        if error is None:

            if not gst_value:

                error = (
                    "GST rate is required."
                )

            else:

                try:

                    gst_rate = Decimal(
                        gst_value
                    )

                    if gst_rate < 0:

                        error = (
                            "GST rate cannot be negative."
                        )

                    elif gst_rate > 100:

                        error = (
                            "GST rate cannot be greater than 100."
                        )

                except InvalidOperation:

                    error = (
                        "Enter a valid GST rate."
                    )

        if error is None:

            Product.objects.create(
                name=name,
                category=category,
                price=price,
                stock=stock,
                gst_rate=gst_rate,
                description=description
            )

            messages.success(
                request,
                "Product added successfully."
            )

            return redirect(
                "add_product"
            )

    return render(
        request,
        "accounts/add_product.html",
        {
            "error": error,
            "form_data": form_data
        }
    )


@login_required(
    login_url="distributor_login"
)
def product_list(request):

    search_query = request.GET.get(
        "search",
        ""
    ).strip()

    products = Product.objects.all()

    if search_query:

        products = products.filter(
            Q(name__icontains=search_query)
            |
            Q(category__icontains=search_query)
            |
            Q(description__icontains=search_query)
        )

    products = products.order_by(
        "-created_at"
    )

    paginator = Paginator(
        products,
        5
    )

    page_number = request.GET.get(
        "page"
    )

    page_obj = paginator.get_page(
        page_number
    )

    return render(
        request,
        "accounts/product_list.html",
        {
            "page_obj": page_obj,
            "search_query": search_query
        }
    )


@login_required(
    login_url="distributor_login"
)
def delete_product(
    request,
    product_id
):

    if request.method != "POST":
        return redirect("product_list")

    product = get_object_or_404(
        Product,
        id=product_id
    )

    product_name = product.name

    try:

        product.delete()

        messages.success(
            request,
            f"Product '{product_name}' deleted successfully."
        )

    except ProtectedError:

        messages.error(
            request,
            f"Cannot delete '{product_name}' because it is already used in an invoice."
        )

    return redirect(
        "product_list"
    )


@login_required(
    login_url="distributor_login"
)
def edit_product(
    request,
    product_id
):

    product = get_object_or_404(
        Product,
        id=product_id
    )

    error = None

    form_data = {
        "name": product.name,
        "category": product.category,
        "price": product.price,
        "stock": product.stock,
        "gst_rate": product.gst_rate,
        "description": product.description
    }

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        category = request.POST.get(
            "category",
            ""
        ).strip()

        price_value = request.POST.get(
            "price",
            ""
        ).strip()

        stock_value = request.POST.get(
            "stock",
            ""
        ).strip()

        gst_value = request.POST.get(
            "gst_rate",
            ""
        ).strip()

        description = request.POST.get(
            "description",
            ""
        ).strip()

        form_data = {
            "name": name,
            "category": category,
            "price": price_value,
            "stock": stock_value,
            "gst_rate": gst_value,
            "description": description
        }

        price = None
        stock = None
        gst_rate = None

        if not name:

            error = (
                "Product name is required."
            )

        elif len(name) < 2:

            error = (
                "Product name must contain "
                "at least 2 characters."
            )

        elif not category:

            error = (
                "Category is required."
            )

        if error is None:

            if not price_value:

                error = (
                    "Price is required."
                )

            else:

                try:

                    price = Decimal(
                        price_value
                    )

                    if not price.is_finite():

                        error = (
                            "Enter a valid price."
                        )

                    elif price <= 0:

                        error = (
                            "Price must be greater than 0."
                        )

                except InvalidOperation:

                    error = (
                        "Enter a valid price."
                    )

        if error is None:

            if stock_value == "":

                error = (
                    "Stock is required."
                )

            else:

                try:

                    stock = int(
                        stock_value
                    )

                    if stock < 0:

                        error = (
                            "Stock cannot be negative."
                        )

                except ValueError:

                    error = (
                        "Stock must be a whole number."
                    )

        if error is None:

            if not gst_value:

                error = (
                    "GST rate is required."
                )

            else:

                try:

                    gst_rate = Decimal(
                        gst_value
                    )

                    if not gst_rate.is_finite():

                        error = (
                            "Enter a valid GST rate."
                        )

                    elif gst_rate < 0:

                        error = (
                            "GST rate cannot be negative."
                        )

                    elif gst_rate > 100:

                        error = (
                            "GST rate cannot be greater than 100."
                        )

                except InvalidOperation:

                    error = (
                        "Enter a valid GST rate."
                    )

        if error is None:

            product.name = name
            product.category = category
            product.price = price
            product.stock = stock
            product.gst_rate = gst_rate
            product.description = description

            product.save()

            messages.success(
                request,
                f"Product '{product.name}' updated successfully."
            )

            return redirect(
                "product_list"
            )

    return render(
        request,
        "accounts/edit_product.html",
        {
            "product": product,
            "form_data": form_data,
            "error": error
        }
    )


@login_required(
        login_url="distributor_login"
)
def create_invoice(request):

    error = None

    created_invoice = None
    created_invoice_id = request.GET.get("created_invoice", "").strip()
    allowed_invoice_ids = request.session.get("created_invoice_ids", [])

    if (
        created_invoice_id.isdigit()
        and int(created_invoice_id) in allowed_invoice_ids
    ):
        created_invoice = Invoice.objects.filter(
            pk=created_invoice_id
        ).first()

    customers = Customer.objects.all().order_by(
        "name"
    )

    products = Product.objects.all().order_by(
        "name"
    )

    selected_customer = ""

    rows = [
        {
            "product_id": "",
            "quantity": "1",
            "discount_rate": "0"
        }
    ]

    if request.method == "POST":

        selected_customer = request.POST.get(
            "customer",
            ""
        ).strip()

        product_ids = request.POST.getlist(
            "product_id"
        )

        quantity_values = request.POST.getlist(
            "quantity"
        )

        submitted_discount_values = request.POST.getlist(
            "discount_rate"
        )

        # Backward compatibility:
        # If the form does not submit discount fields,
        # treat every product row as having 0% discount.
        if submitted_discount_values:

            discount_values = submitted_discount_values

        else:

            discount_values = [
                "0"
                for _ in product_ids
            ]

        rows = []

        row_count = max(
            len(product_ids),
            len(quantity_values),
            len(discount_values)
        )

        for index in range(row_count):

            product_id = (
                product_ids[index]
                if index < len(product_ids)
                else ""
            )

            quantity = (
                quantity_values[index]
                if index < len(quantity_values)
                else "1"
            )

            discount_rate = (
                discount_values[index]
                if index < len(discount_values)
                else "0"
            )

            rows.append(
                {
                    "product_id": product_id,
                    "quantity": quantity,
                    "discount_rate": discount_rate
                }
            )

        if not rows:

            rows = [
                {
                    "product_id": "",
                    "quantity": "1",
                    "discount_rate": "0"
                }
            ]

        customer = None

        if selected_customer.isdigit():

            customer = Customer.objects.filter(
                id=selected_customer
            ).first()

        if customer is None:

            error = (
                "Please select a valid customer."
            )

        elif not product_ids:

            error = (
                "Please add at least one product."
            )

        elif len(product_ids) != len(quantity_values):

            error = (
                "Invalid product rows. "
                "Please try again."
            )

        elif (
            submitted_discount_values
            and len(submitted_discount_values) != len(product_ids)
        ):

            error = (
                "Invalid discount rows. "
                "Please try again."
            )

        validated_items = []

        if error is None:

            for index, (
                product_id,
                quantity_value,
                discount_value
            ) in enumerate(
                zip(
                    product_ids,
                    quantity_values,
                    discount_values
                ),
                start=1
            ):

                if not product_id.strip():

                    error = (
                        f"Please select a product "
                        f"in row {index}."
                    )

                    break

                if not product_id.isdigit():

                    error = (
                        f"Invalid product in row {index}."
                    )

                    break

                if not quantity_value.strip():

                    error = (
                        f"Quantity is required "
                        f"in row {index}."
                    )

                    break

                if not quantity_value.isdigit():

                    error = (
                        f"Quantity must be a whole number "
                        f"in row {index}."
                    )

                    break

                quantity = int(
                    quantity_value
                )

                if quantity <= 0:

                    error = (
                        f"Quantity must be greater than "
                        f"zero in row {index}."
                    )

                    break

                # Validate discount percentage.
                if not discount_value.strip():

                    error = (
                        f"Discount percentage is required "
                        f"in row {index}."
                    )

                    break

                try:

                    discount_rate = Decimal(
                        discount_value
                    )

                    if not discount_rate.is_finite():

                        error = (
                            f"Enter a valid discount percentage "
                            f"in row {index}."
                        )

                        break

                    if discount_rate < 0:

                        error = (
                            f"Discount cannot be negative "
                            f"in row {index}."
                        )

                        break

                    if discount_rate > 100:

                        error = (
                            f"Discount cannot be greater than "
                            f"100% in row {index}."
                        )

                        break

                    discount_rate = discount_rate.quantize(
                        Decimal("0.01"),
                        rounding=ROUND_HALF_UP
                    )

                except (
                    InvalidOperation,
                    TypeError,
                    ValueError
                ):

                    error = (
                        f"Enter a valid discount percentage "
                        f"in row {index}."
                    )

                    break

                product = Product.objects.filter(
                    id=product_id
                ).first()

                if product is None:

                    error = (
                        f"Selected product in row "
                        f"{index} does not exist."
                    )

                    break

                try:

                    unit_price = Decimal(
                        str(product.price)
                    )

                    gst_rate = Decimal(
                        str(product.gst_rate)
                    )

                    if (
                        not unit_price.is_finite()
                        or unit_price <= 0
                    ):

                        error = (
                            f"Invalid price for "
                            f"{product.name}."
                        )

                        break

                    if (
                        not gst_rate.is_finite()
                        or gst_rate < 0
                        or gst_rate > 100
                    ):

                        error = (
                            f"Invalid GST rate for "
                            f"{product.name}."
                        )

                        break

                except (
                    InvalidOperation,
                    TypeError,
                    ValueError
                ):

                    error = (
                        f"Invalid price or GST for "
                        f"{product.name}."
                    )

                    break

                # 1. Calculate original line subtotal.
                line_subtotal = (
                    unit_price * quantity
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )

                # 2. Calculate discount amount.
                discount_amount = (
                    line_subtotal
                    * discount_rate
                    / Decimal("100")
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )

                # 3. Calculate taxable amount after discount.
                taxable_amount = (
                    line_subtotal - discount_amount
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )

                # 4. Calculate GST on taxable amount.
                line_gst = (
                    taxable_amount
                    * gst_rate
                    / Decimal("100")
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )

                # 5. Calculate final product row total.
                line_final_total = (
                    taxable_amount + line_gst
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )

                validated_items.append(
                    {
                        "product": product,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "gst_rate": gst_rate,
                        "discount_rate": discount_rate,
                        "line_total": line_subtotal,
                        "discount_amount": discount_amount,
                        "taxable_amount": taxable_amount,
                        "line_gst": line_gst,
                        "line_final_total": line_final_total
                    }
                )

        if error is None:

            # Total before discount.
            subtotal = sum(
                (
                    item["line_total"]
                    for item in validated_items
                ),
                Decimal("0.00")
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            # Total discount across all product rows.
            total_discount = sum(
                (
                    item["discount_amount"]
                    for item in validated_items
                ),
                Decimal("0.00")
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            # Total taxable amount after discount.
            taxable_amount = (
                subtotal - total_discount
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            # Total GST after applying discounts.
            gst_amount = sum(
                (
                    item["line_gst"]
                    for item in validated_items
                ),
                Decimal("0.00")
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            # Final invoice amount.
            grand_total = (
                taxable_amount + gst_amount
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            invoice_number = (
                f"INV-{timezone.localdate():%Y%m%d}-"
                f"{uuid4().hex[:8].upper()}"
            )

            with transaction.atomic():

                invoice = Invoice.objects.create(
                    invoice_number=invoice_number,
                    customer=customer,
                    subtotal=subtotal,
                    discount_amount=total_discount,
                    gst_amount=gst_amount,
                    grand_total=grand_total
                )

                invoice_items = []

                for item in validated_items:

                    invoice_items.append(
                        InvoiceItem(
                            invoice=invoice,
                            product=item["product"],
                            quantity=item["quantity"],
                            unit_price=item["unit_price"],
                            gst_rate=item["gst_rate"],
                            discount_rate=item["discount_rate"],
                            discount_amount=item["discount_amount"],
                            line_total=item["line_total"]
                        )
                    )

                InvoiceItem.objects.bulk_create(
                    invoice_items
                )

            created_invoice_ids = request.session.get(
                "created_invoice_ids",
                []
            )

            if not isinstance(created_invoice_ids, list):
                created_invoice_ids = []

            created_invoice_ids.append(invoice.pk)

            request.session["created_invoice_ids"] = (
                created_invoice_ids[-100:]
            )

            messages.success(
                request,
                (
                    f"Invoice {invoice.invoice_number} "
                    f"created successfully. "
                    f"Grand Total: â‚¹{grand_total}"
                )
            )

            from django.urls import reverse

            return redirect(
                f"{reverse('create_invoice')}?created_invoice={invoice.pk}"
            )

    return render(
        request,
        "accounts/create_invoice.html",
        {
            "customers": customers,
            "products": products,
            "rows": rows,
            "selected_customer": selected_customer,
            "error": error,
            "created_invoice": created_invoice
        }
    )


@login_required
def dashboard(request):

    return render(
        request,
        "accounts/dashboard.html"
    )


@login_required(login_url="distributor_login")
def download_invoice_pdf(request, invoice_id):
    """Generate a branded PDF for an invoice created in this session."""

    from io import BytesIO
    from pathlib import Path
    from xml.sax.saxutils import escape

    from django.conf import settings
    from django.http import Http404, HttpResponse

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm

    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode import qr as reportlab_qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Flowable,
        Image as ReportLabImage,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    class InvoiceQRFlowable(Flowable):
        def __init__(self, value, size=24 * mm):
            super().__init__()

            qr_widget = reportlab_qr.QrCodeWidget(value)
            x1, y1, x2, y2 = qr_widget.getBounds()

            qr_width = x2 - x1
            qr_height = y2 - y1

            if qr_width <= 0 or qr_height <= 0:
                raise ValueError("Could not generate invoice QR code.")

            scale_x = size / qr_width
            scale_y = size / qr_height

            self.drawing = Drawing(
                size,
                size,
                transform=[
                    scale_x, 0, 0, scale_y,
                    -x1 * scale_x, -y1 * scale_y,
                ],
            )
            self.drawing.add(qr_widget)

            self.width = size
            self.height = size

        def draw(self):
            renderPDF.draw(self.drawing, self.canv, 0, 0)

    allowed_invoice_ids = request.session.get(
        "created_invoice_ids",
        []
    )

    if invoice_id not in allowed_invoice_ids:
        raise Http404("Invoice not found.")

    invoice = get_object_or_404(
        Invoice.objects.select_related("customer").prefetch_related(
            "items__product"
        ),
        pk=invoice_id
    )

    profile = DistributorProfile.objects.filter(
        user=request.user
    ).first()

    # Use an available Unicode font where possible.
    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"

    font_candidates = [
        Path("C:/Windows/Fonts/Nirmala.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansGujarati-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path(settings.BASE_DIR) / "static/fonts/NotoSansGujarati-Regular.ttf",
    ]

    for font_path in font_candidates:
        if font_path.exists():
            try:
                pdfmetrics.registerFont(
                    TTFont("InvoiceUnicode", str(font_path))
                )
                font_regular = "InvoiceUnicode"
                font_bold = "InvoiceUnicode"
                break
            except Exception:
                continue

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="PdfBrand",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#1D4D40"),
        spaceAfter=3
    ))

    styles.add(ParagraphStyle(
        name="PdfSmall",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#53645D")
    ))

    styles.add(ParagraphStyle(
        name="PdfTitle",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=16,
        leading=19,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#1D4D40")
    ))

    styles.add(ParagraphStyle(
        name="PdfSection",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1D4D40"),
        spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        name="PdfCell",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=9,
        leading=12
    ))

    styles.add(ParagraphStyle(
        name="PdfRight",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=9,
        leading=12,
        alignment=TA_RIGHT
    ))

    styles.add(ParagraphStyle(
        name="PdfHeader",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.white
    ))

    styles.add(ParagraphStyle(
        name="PdfGrand",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1D4D40")
    ))

    def safe(value):
        return escape(
            str(value or "")
        ).replace("\r\n", "<br/>").replace("\n", "<br/>")

    def money(value):
        amount = Decimal(str(value or "0"))
        return f"INR {amount:,.2f}"

    business_name = (
        profile.business_name.strip()
        if profile and profile.business_name
        else (
            request.user.get_full_name()
            or request.user.username
            or "Business"
        )
    )

    business_address = profile.business_address if profile else ""
    business_phone = profile.phone if profile else ""
    business_gstin = profile.gstin if profile else ""

    brand_details = []

    if business_address:
        brand_details.append(business_address)

    if business_phone:
        brand_details.append(f"Phone: {business_phone}")

    if request.user.email:
        brand_details.append(f"Email: {request.user.email}")

    if business_gstin:
        brand_details.append(f"GSTIN: {business_gstin}")

    brand_info = [
        Paragraph(safe(business_name), styles["PdfBrand"]),
        Paragraph(
            "<br/>".join(safe(value) for value in brand_details) or " ",
            styles["PdfSmall"]
        )
    ]

    # Load the uploaded company logo if available.
    logo_element = Paragraph(" ", styles["PdfSmall"])

    if profile and profile.logo:
        try:
            profile.logo.open("rb")
            logo_data = BytesIO(profile.logo.read())
            profile.logo.close()
            logo_data.seek(0)

            logo_element = ReportLabImage(
                logo_data,
                width=28 * mm,
                height=22 * mm,
                kind="proportional"
            )
        except Exception:
            try:
                profile.logo.close()
            except Exception:
                pass

    story = []

    invoice_heading = (
        "DRAFT INVOICE"
        if invoice.status == "DRAFT"
        else "TAX INVOICE"
    )

    header_table = Table(
        [[
            logo_element,
            brand_info,
            Paragraph(safe(invoice_heading), styles["PdfTitle"])
        ]],
        colWidths=[30 * mm, 99 * mm, 45 * mm]
    )

    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F6F3")),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#D6E3DC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 16))

    # Customer information.
    customer_lines = [
        f"<b>{safe(invoice.customer.name)}</b>"
    ]

    if invoice.customer.address:
        customer_lines.append(safe(invoice.customer.address))

    if invoice.customer.phone:
        customer_lines.append(f"Phone: {safe(invoice.customer.phone)}")

    if invoice.customer.email:
        customer_lines.append(f"Email: {safe(invoice.customer.email)}")

    bill_to = [
        Paragraph("BILL TO", styles["PdfSection"]),
        Paragraph("<br/>".join(customer_lines), styles["PdfSmall"])
    ]

    invoice_lines = [
        f"<b>Invoice No:</b> {safe(invoice.invoice_number)}",
        f"<b>Date:</b> {safe(invoice.invoice_date.strftime('%d %b %Y'))}",
        f"<b>Status:</b> {safe(invoice.get_status_display())}"
    ]

    invoice_details = [
        Paragraph("INVOICE DETAILS", styles["PdfSection"]),
        Paragraph("<br/>".join(invoice_lines), styles["PdfSmall"])
    ]

    details_table = Table(
        [[bill_to, invoice_details]],
        colWidths=[87 * mm, 87 * mm]
    )

    details_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAF9")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D6E3DC")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E1E8E4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
    ]))

    story.append(details_table)
    story.append(Spacer(1, 18))

    # Product and tax details.
    item_rows = [[
        Paragraph("PRODUCT", styles["PdfHeader"]),
        Paragraph("QTY", styles["PdfHeader"]),
        Paragraph("UNIT PRICE", styles["PdfHeader"]),
        Paragraph("DISCOUNT", styles["PdfHeader"]),
        Paragraph("GST", styles["PdfHeader"]),
        Paragraph("LINE TOTAL", styles["PdfHeader"]),
    ]]

    for item in invoice.items.all():
        original_total = Decimal(str(item.line_total))
        discount_amount = Decimal(str(item.discount_amount))
        discount_rate = Decimal(str(item.discount_rate))
        gst_rate = Decimal(str(item.gst_rate))

        taxable_amount = original_total - discount_amount

        line_gst = (
            taxable_amount * gst_rate / Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        final_line_total = taxable_amount + line_gst

        item_rows.append([
            Paragraph(safe(item.product.name), styles["PdfCell"]),
            Paragraph(str(item.quantity), styles["PdfRight"]),
            Paragraph(money(item.unit_price), styles["PdfRight"]),
            Paragraph(
                f"{discount_rate:.2f}%<br/>{money(discount_amount)}",
                styles["PdfRight"]
            ),
            Paragraph(f"{gst_rate:.2f}%", styles["PdfRight"]),
            Paragraph(money(final_line_total), styles["PdfRight"]),
        ])

    if len(item_rows) == 1:
        item_rows.append([
            Paragraph("No items recorded.", styles["PdfCell"]),
            "", "", "", "", ""
        ])

    items_table = Table(
        item_rows,
        colWidths=[
            60 * mm,
            15 * mm,
            24 * mm,
            30 * mm,
            17 * mm,
            28 * mm
        ],
        repeatRows=1
    )

    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4D40")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9E2DD")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#F7FAF8")
        ]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    story.append(items_table)
    story.append(Spacer(1, 16))

    subtotal = Decimal(str(invoice.subtotal))
    discount_total = Decimal(str(invoice.discount_amount))
    taxable_total = subtotal - discount_total
    gst_total = Decimal(str(invoice.gst_amount))
    grand_total = Decimal(str(invoice.grand_total))

    totals_rows = [
        [
            Paragraph("Subtotal", styles["PdfCell"]),
            Paragraph(money(subtotal), styles["PdfRight"])
        ],
        [
            Paragraph("Discount", styles["PdfCell"]),
            Paragraph(money(discount_total), styles["PdfRight"])
        ],
        [
            Paragraph("Taxable Amount", styles["PdfCell"]),
            Paragraph(money(taxable_total), styles["PdfRight"])
        ],
        [
            Paragraph("GST", styles["PdfCell"]),
            Paragraph(money(gst_total), styles["PdfRight"])
        ],
        [
            Paragraph("GRAND TOTAL", styles["PdfGrand"]),
            Paragraph(money(grand_total), styles["PdfGrand"])
        ],
    ]

    totals_table = Table(
        totals_rows,
        colWidths=[42 * mm, 38 * mm],
        hAlign="RIGHT"
    )

    totals_table.setStyle(TableStyle([
        ("LINEABOVE", (0, -1), (-1, -1), 1.1, colors.HexColor("#1D4D40")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EAF3EE")),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(totals_table)
    story.append(Spacer(1, 10))

    # Dynamically retrieve invoice items and product details.
    invoice_items = invoice.items.select_related("product").all()

    product_summary = []
    for index, item in enumerate(invoice_items, start=1):
        product_name = " ".join(str(item.product.name).split())
        product_summary.append(
            f"{index}. {product_name} | "
            f"Qty: {item.quantity} | "
            f"Line Total: INR {item.line_total:.2f}"
        )

    # Generate complete dynamic QR content from database records.
    qr_payload_lines = [
        "ADVANCE BILLING SYSTEM - INVOICE",
        f"Invoice No: {invoice.invoice_number}",
        f"Date: {invoice.invoice_date.strftime('%d %b %Y')}",
        f"Customer: {invoice.customer.name}",
        f"Grand Total: INR {invoice.grand_total:.2f}",
        f"Status: {invoice.get_status_display()}",
        "",
        "PRODUCT SUMMARY:",
    ]

    qr_payload_lines.extend(
        product_summary if product_summary else ["No products found."]
    )

    qr_payload = "\n".join(qr_payload_lines)

    qr_details = [
        Paragraph(
            "SCAN FOR INVOICE SUMMARY",
            styles["PdfSection"],
        ),
        Paragraph(
            "Scan this QR code with your phone camera or QR scanner "
            "to read the invoice details.",
            styles["PdfSmall"],
        ),
        Spacer(1, 4),
        Paragraph(
            f"<b>Invoice No:</b> {safe(invoice.invoice_number)}",
            styles["PdfSmall"],
        ),
    ]

    qr_card = Table(
        [[
            InvoiceQRFlowable(qr_payload, size=24 * mm),
            qr_details,
        ]],
        colWidths=[38 * mm, 136 * mm],
        hAlign="LEFT",
    )

    qr_card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAF9")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D6E3DC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    story.append(qr_card)
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        "Thank you for your business.",
        styles["PdfSection"]
    ))

    story.append(Paragraph(
        "This is a computer-generated invoice.",
        styles["PdfSmall"]
    ))

    buffer = BytesIO()

    def draw_footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D6E3DC"))
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
        canvas.setFont(font_regular, 7)
        canvas.setFillColor(colors.HexColor("#64736C"))
        canvas.drawString(18 * mm, 8 * mm, business_name[:80])
        canvas.drawRightString(
            A4[0] - 18 * mm,
            8 * mm,
            f"Page {document.page}"
        )
        canvas.restoreState()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
        title=f"Invoice {invoice.invoice_number}",
        author=business_name
    )

    document.build(
        story,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer
    )

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/pdf"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{invoice.invoice_number}.pdf"'
    )

    buffer.close()
    return response
