import random
from datetime import timedelta

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.utils import timezone

from .models import OTPVerification


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

    return render(request, "accounts/admin_login.html")


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
            return redirect("dashboard")

        return render(
            request,
            "accounts/distributor_login.html",
            {"error": "Invalid username or password"}
        )

    return render(request, "accounts/distributor_login.html")


def distributor_register(request):
    return render(
        request,
        "accounts/distributor_register.html"
    )


def generate_otp(request):
    message = None

    if request.method == "POST":
        email = request.POST.get("email", "").strip()

        if email:
            expiry_time = timezone.now() - timedelta(minutes=5)

            OTPVerification.objects.filter(
                created_at__lt=expiry_time
            ).delete()

            OTPVerification.objects.filter(
                email=email
            ).delete()

            otp_code = str(
                random.randint(100000, 999999)
            )

            OTPVerification.objects.create(
                email=email,
                otp_code=otp_code
            )

            request.session["otp_email"] = email

            print(
                f"OTP for {email}: {otp_code}"
            )

            message = "OTP generated successfully."

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
            error = "Please generate an OTP first."

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


@login_required
def dashboard(request):
    return render(
        request,
        "accounts/dashboard.html"
    )