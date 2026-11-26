import secrets
from django.db import IntegrityError
from django.views.decorators.http import require_POST
from django.contrib.auth.password_validation import validate_password
from django.http import JsonResponse
import json
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
from .decorators import distributor_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Q
from django.core.mail import send_mail
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
    Payment,
)


@require_POST
def customer_register_api(request):
    """Register a customer through the Distributor API."""

    if not request.user.is_authenticated:
        return JsonResponse({
            "success": False,
            "message": "Distributor login required."
        }, status=401)

    if not DistributorProfile.objects.filter(user=request.user).exists():
        return JsonResponse({
            "success": False,
            "message": "Only registered distributors can add customers."
        }, status=403)

    if request.content_type == "application/json":
        try:
            data = json.loads(request.body or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({
                "success": False,
                "message": "Invalid JSON data."
            }, status=400)

        if not isinstance(data, dict):
            return JsonResponse({
                "success": False,
                "message": "JSON data must be an object."
            }, status=400)
    else:
        data = request.POST

    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    phone = str(data.get("phone") or "").strip()
    address = str(data.get("address") or "").strip()

    if not all([name, email, phone, address]):
        return JsonResponse({
            "success": False,
            "message": "Name, email, phone and address are required."
        }, status=400)

    if len(name) < 2 or not re.fullmatch(r"[A-Za-z ]+", name):
        return JsonResponse({
            "success": False,
            "message": "Enter a valid customer name using letters and spaces."
        }, status=400)

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({
            "success": False,
            "message": "Enter a valid email address."
        }, status=400)

    if not phone.isdigit() or len(phone) != 10:
        return JsonResponse({
            "success": False,
            "message": "Phone number must contain exactly 10 digits."
        }, status=400)

    if len(address) < 5:
        return JsonResponse({
            "success": False,
            "message": "Please enter a valid address."
        }, status=400)

    if Customer.objects.filter(distributor=request.user.distributor_profile, email__iexact=email).exists():
        return JsonResponse({
            "success": False,
            "message": "A customer with this email already exists."
        }, status=409)

    try:
        customer = Customer.objects.create(
            distributor=request.user.distributor_profile,
            name=name,
            email=email,
            phone=phone,
            address=address
        )
    except IntegrityError:
        return JsonResponse({
            "success": False,
            "message": "A customer with this email already exists."
        }, status=409)

    return JsonResponse({
        "success": True,
        "message": "Customer registered successfully.",
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "address": customer.address
        }
    }, status=201)


@distributor_required
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
            if Customer.objects.filter(distributor=request.user.distributor_profile, email__iexact=email).exists():
                error = "A customer with this email already exists."
            else:
                try:
                    Customer.objects.create(
            distributor=request.user.distributor_profile,
            name=name,
                        email=email,
                        phone=phone,
                        address=address
                    )
                except IntegrityError:
                    error = "A customer with this email already exists."
                else:
                    success = "Customer added successfully."
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


@distributor_required
def customer_list(request):

    search_query = request.GET.get(
        "search",
        ""
    ).strip()

    customers = Customer.objects.filter(distributor=request.user.distributor_profile)

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


@distributor_required
def edit_customer(
    request,
    customer_id
):

    customer = get_object_or_404(Customer, id=customer_id, distributor=request.user.distributor_profile)

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
                    distributor=request.user.distributor_profile,
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


@distributor_required
def delete_customer(
    request,
    customer_id
):

    customer = get_object_or_404(Customer, id=customer_id, distributor=request.user.distributor_profile)

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

