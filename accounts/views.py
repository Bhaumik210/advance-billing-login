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

    phone = "Not added"

    try:

        phone = (
            request.user
            .distributor_profile
            .phone
        )

    except DistributorProfile.DoesNotExist:
        pass

    return render(
        request,
        "accounts/distributor_profile.html",
        {
            "phone": phone
        }
    )


@login_required(
    login_url="distributor_login"
)
def edit_distributor_profile(request):

    user = request.user

    profile, created = (
        DistributorProfile.objects
        .get_or_create(
            user=user,
            defaults={
                "phone": ""
            }
        )
    )

    error = None

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

        if not full_name:

            error = (
                "Full name is required."
            )

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

            duplicate_email = (
                User.objects
                .filter(
                    email__iexact=email
                )
                .exclude(
                    id=user.id
                )
                .exists()
            )

            if duplicate_email:

                error = (
                    "This email is already "
                    "used by another account."
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

            name_parts = full_name.split(
                " ",
                1
            )

            user.first_name = name_parts[0]

            if len(name_parts) > 1:
                user.last_name = name_parts[1]
            else:
                user.last_name = ""

            user.email = email
            profile.phone = phone

            with transaction.atomic():

                user.save()
                profile.save()

            messages.success(
                request,
                "Profile updated successfully."
            )

            return redirect(
                "distributor_profile"
            )

    return render(
        request,
        "accounts/edit_distributor_profile.html",
        {
            "error": error,
            "profile": profile
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

            messages.success(
                request,
                (
                    f"Invoice {invoice.invoice_number} "
                    f"created successfully. "
                    f"Grand Total: ₹{grand_total}"
                )
            )

            return redirect(
                "create_invoice"
            )

    return render(
        request,
        "accounts/create_invoice.html",
        {
            "customers": customers,
            "products": products,
            "rows": rows,
            "selected_customer": selected_customer,
            "error": error
        }
    )


@login_required
def dashboard(request):

    return render(
        request,
        "accounts/dashboard.html"
    )