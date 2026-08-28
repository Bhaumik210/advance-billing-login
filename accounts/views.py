import random
from datetime import timedelta

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.db import transaction

from .models import OTPVerification, DistributorProfile


@never_cache
@ensure_csrf_cookie
def admin_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

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
            {"error": "Invalid username or password"}
        )

    return render(
        request,
        "accounts/admin_login.html"
    )


@never_cache
@ensure_csrf_cookie
def distributor_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect("distributor_profile")

        return render(
            request,
            "accounts/distributor_login.html",
            {"error": "Invalid username or password"}
        )

    return render(
        request,
        "accounts/distributor_login.html"
    )


def distributor_register(request):
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

        password = request.POST.get(
            "password",
            ""
        )

        if not full_name or not email or not phone or not password:
            error = "All fields are required."

        elif not phone.isdigit() or len(phone) != 10:
            error = "Enter a valid 10-digit phone number."

        elif User.objects.filter(
            username=email
        ).exists():
            error = "This email is already registered."

        elif User.objects.filter(
            email=email
        ).exists():
            error = "This email is already registered."

        else:
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
                "Registration successful. Please login to continue."
            )

            return redirect(
                "distributor_login"
            )

    return render(
        request,
        "accounts/distributor_register.html",
        {
            "error": error
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


@login_required
def dashboard(request):
    return render(
        request,
        "accounts/dashboard.html"
    )