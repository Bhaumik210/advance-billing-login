import random
import re

from datetime import timedelta

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

from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from .models import (
    OTPVerification,
    DistributorProfile,
    Customer,
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
            login(request, user)
            return redirect("dashboard")

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
            login(request, user)

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
            error = "Email address is required."

        else:
            try:
                validate_email(email)

            except ValidationError:
                error = (
                    "Enter a valid email address."
                )

        if error is None:

            if not phone:
                error = "Phone number is required."

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
                error = "Password is required."

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
                error = "Invalid OTP."

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
            error = "Email address is required."

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
                error = "Phone number is required."

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


# Task 6 - Customer List

@login_required(
    login_url="distributor_login"
)
def customer_list(request):

    customers = (
        Customer.objects
        .all()
        .order_by("-created_at")
    )

    return render(
        request,
        "accounts/customer_list.html",
        {
            "customers": customers
        }
    )


# Task 6 - Delete Customer

@login_required(
    login_url="distributor_login"
)
@login_required(login_url="distributor_login")
def edit_customer(request, customer_id):

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
            error = "Customer name is required."

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
            error = "Email address is required."

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
                .filter(email__iexact=email)
                .exclude(id=customer.id)
                .exists()
            )

            if duplicate_email:
                error = (
                    "Another customer already uses "
                    "this email address."
                )

        if error is None:

            if not phone:
                error = "Phone number is required."

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
                error = "Address is required."

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
def delete_customer(request, customer_id):

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


@login_required
def dashboard(request):

    return render(
        request,
        "accounts/dashboard.html"
    )