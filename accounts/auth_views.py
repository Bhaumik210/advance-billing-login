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
    logout as auth_logout,
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


@never_cache
@ensure_csrf_cookie
def admin_register(request):
    return render(
        request,
        "accounts/admin_register.html"
    )


@never_cache
@require_POST
def admin_register_api(request):
    """Create a normal application Admin user account."""
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"success": False, "message": "Invalid JSON data."}, status=400)
    else:
        data = request.POST

    full_name = str(data.get("full_name", "")).strip()
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    confirm_password = str(data.get("confirm_password", ""))

    if not all([full_name, username, email, password, confirm_password]):
        return JsonResponse({"success": False, "message": "All required fields must be filled."}, status=400)

    if password != confirm_password:
        return JsonResponse({"success": False, "message": "Passwords do not match."}, status=400)

    try:
        validate_email(email)
        User._meta.get_field("username").clean(username, None)
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        elif not re.search(r"[A-Z]", password):
            raise ValidationError("Password must contain at least one uppercase letter.")
        elif not re.search(r"[a-z]", password):
            raise ValidationError("Password must contain at least one lowercase letter.")
        elif not re.search(r"[0-9]", password):
            raise ValidationError("Password must contain at least one number.")

        validate_password(password)
    except ValidationError as error:
        return JsonResponse({"success": False, "message": error.messages}, status=400)

    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({"success": False, "message": "Username already exists."}, status=400)

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"success": False, "message": "Email already registered."}, status=400)

    name_parts = full_name.split()
    first_name = name_parts[0]
    last_name = " ".join(name_parts[1:])

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=False,
                is_superuser=False,
            )
    except IntegrityError:
        return JsonResponse({"success": False, "message": "Username or email already exists."}, status=400)

    return JsonResponse({
        "success": True,
        "message": "Admin account registered successfully.",
        "user": {
            "id": user.id,
            "full_name": user.get_full_name(),
            "username": user.username,
            "email": user.email,
        },
    }, status=201)


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

        if (
            user is not None
            and not DistributorProfile.objects.filter(user=user).exists()
        ):

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

        if (
            user is not None
            and DistributorProfile.objects.filter(user=user).exists()
        ):

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


@require_POST
def user_logout(request):
    is_distributor = (
        request.user.is_authenticated
        and DistributorProfile.objects.filter(user=request.user).exists()
    )

    auth_logout(request)
    messages.success(request, "You have been logged out successfully.")

    if is_distributor:
        return redirect("distributor_login")

    return redirect("admin_login")

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
    error = None

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        try:
            validate_email(email)
        except ValidationError:
            error = "Please enter a valid email address."
        else:
            # Avoid revealing whether an account exists.
            user = User.objects.filter(email__iexact=email).first()

            if user:
                OTPVerification.objects.filter(
                    created_at__lt=timezone.now() - timedelta(minutes=5)
                ).delete()

                OTPVerification.objects.filter(email__iexact=email).delete()

                otp_code = str(secrets.randbelow(900000) + 100000)
                record = OTPVerification.objects.create(
                    email=email,
                    otp_code=otp_code
                )

                try:
                    send_mail(
                        subject="Password Reset OTP - Advance Billing System",
                        message=(
                            f"Your password reset OTP is {otp_code}. "
                            "It is valid for 5 minutes. "
                            "If you did not request this, ignore this email."
                        ),
                        from_email=None,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                except Exception:
                    record.delete()
                    error = "Unable to send OTP. Please try again later."
                else:
                    request.session["otp_email"] = email
                    request.session.pop("otp_attempts", None)
                    message = (
                        "If an account exists with this email, "
                        "a password reset OTP has been sent. "
                        "Check your email or development terminal."
                    )
            else:
                message = (
                    "If an account exists with this email, "
                    "a password reset OTP has been sent."
                )

    return render(
        request,
        "accounts/otp_generate.html",
        {"message": message, "error": error}
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
    message = None
    error = None

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        otp_code = request.POST.get("otp", "").strip()
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not all([email, otp_code, new_password, confirm_password]):
            error = "Please fill in all fields."
        elif not re.fullmatch(r"[0-9]{6}", otp_code):
            error = "Enter a valid 6-digit OTP."
        elif new_password != confirm_password:
            error = "Passwords do not match."
        elif request.session.get("otp_email") != email:
            error = "Please generate a new OTP for this email address."
        else:
            user = User.objects.filter(email__iexact=email).first()
            otp_record = (
                OTPVerification.objects
                .filter(email__iexact=email)
                .order_by("-created_at")
                .first()
            )

            if user is None or otp_record is None:
                error = "OTP not found. Please generate a new OTP."
            elif otp_record.is_expired():
                otp_record.delete()
                request.session.pop("otp_email", None)
                error = "OTP has expired. Please generate a new OTP."
            elif otp_record.otp_code != otp_code:
                attempts = request.session.get("otp_attempts", 0) + 1
                request.session["otp_attempts"] = attempts

                if attempts >= 5:
                    otp_record.delete()
                    request.session.pop("otp_email", None)
                    request.session.pop("otp_attempts", None)
                    error = "Too many incorrect attempts. Generate a new OTP."
                else:
                    error = f"Invalid OTP. Attempts remaining: {5 - attempts}."
            else:
                try:
                    validate_password(new_password, user)
                except ValidationError as exc:
                    error = " ".join(exc.messages)
                else:
                    with transaction.atomic():
                        user.set_password(new_password)
                        user.save(update_fields=["password"])
                        otp_record.delete()

                    request.session.pop("otp_email", None)
                    request.session.pop("otp_attempts", None)
                    messages.success(
                        request,
                        "Password reset successfully. Please log in with your new password."
                    )
                    return redirect("distributor_login")

    return render(
        request,
        "accounts/forgot_password.html",
        {"error": error, "message": message}
    )


def _get_application_admin(email):
    """Return an application Admin account, never a Distributor account."""
    users = User.objects.filter(email__iexact=email).order_by("id")
    for user in users:
        if not DistributorProfile.objects.filter(user=user).exists():
            return user
    return None


def admin_generate_otp(request):
    message = None
    error = None

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        try:
            validate_email(email)
        except ValidationError:
            error = "Please enter a valid email address."
        else:
            admin_user = _get_application_admin(email)

            if admin_user:
                OTPVerification.objects.filter(
                    created_at__lt=timezone.now() - timedelta(minutes=5)
                ).delete()
                OTPVerification.objects.filter(
                    email__iexact=email
                ).delete()

                otp_code = str(secrets.randbelow(900000) + 100000)
                record = OTPVerification.objects.create(
                    email=email,
                    otp_code=otp_code
                )

                try:
                    send_mail(
                        subject="Admin Password Reset OTP - Advance Billing System",
                        message=(
                            f"Your Admin password reset OTP is {otp_code}. "
                            "It is valid for 5 minutes. "
                            "If you did not request this, ignore this email."
                        ),
                        from_email=None,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                except Exception:
                    record.delete()
                    error = "Unable to send OTP. Please try again later."
                else:
                    request.session["admin_otp_email"] = email
                    request.session.pop("admin_otp_attempts", None)
                    message = (
                        "An OTP has been sent if this email belongs to "
                        "an Admin account. Check your email or development terminal."
                    )
            else:
                message = (
                    "If this email belongs to an Admin account, "
                    "an OTP has been sent."
                )

    return render(
        request,
        "accounts/admin_otp_generate.html",
        {"message": message, "error": error}
    )


def admin_forgot_password(request):
    message = None
    error = None

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        otp_code = request.POST.get("otp", "").strip()
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not all([email, otp_code, new_password, confirm_password]):
            error = "Please fill in all fields."
        elif not re.fullmatch(r"[0-9]{6}", otp_code):
            error = "Enter a valid 6-digit OTP."
        elif new_password != confirm_password:
            error = "Passwords do not match."
        elif request.session.get("admin_otp_email") != email:
            error = "Please generate a new Admin OTP for this email address."
        else:
            admin_user = _get_application_admin(email)
            otp_record = (
                OTPVerification.objects
                .filter(email__iexact=email)
                .order_by("-created_at")
                .first()
            )

            if admin_user is None:
                error = "Admin account or OTP not found. Please generate a new OTP."
            elif otp_record is None:
                error = "OTP not found. Please generate a new OTP."
            elif otp_record.is_expired():
                otp_record.delete()
                request.session.pop("admin_otp_email", None)
                request.session.pop("admin_otp_attempts", None)
                error = "OTP has expired. Please generate a new OTP."
            elif otp_record.otp_code != otp_code:
                attempts = request.session.get("admin_otp_attempts", 0) + 1
                request.session["admin_otp_attempts"] = attempts

                if attempts >= 5:
                    otp_record.delete()
                    request.session.pop("admin_otp_email", None)
                    request.session.pop("admin_otp_attempts", None)
                    error = "Too many incorrect attempts. Generate a new OTP."
                else:
                    error = (
                        f"Invalid OTP. Attempts remaining: {5 - attempts}."
                    )
            else:
                try:
                    validate_password(new_password, admin_user)
                except ValidationError as exc:
                    error = " ".join(exc.messages)
                else:
                    with transaction.atomic():
                        admin_user.set_password(new_password)
                        admin_user.save(update_fields=["password"])
                        otp_record.delete()

                    request.session.pop("admin_otp_email", None)
                    request.session.pop("admin_otp_attempts", None)
                    messages.success(
                        request,
                        "Admin password reset successfully. Please log in."
                    )
                    return redirect("admin_login")

    return render(
        request,
        "accounts/admin_forgot_password.html",
        {
            "error": error,
            "message": message,
            "email": request.session.get("admin_otp_email", "")
        }
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
