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


@login_required(login_url='distributor_login')
def invoice_payments(request, invoice_id):
    from datetime import date

    invoice = get_object_or_404(Invoice, pk=invoice_id)

    payment_history = invoice.payments.order_by("-payment_date", "-id")
    paid_amount = sum(
        (payment.amount for payment in payment_history),
        Decimal("0.00")
    )
    balance = invoice.grand_total - paid_amount
    error = None

    if request.method == "POST":
        if invoice.status in ("DRAFT", "CANCELLED", "PAID"):
            error = "Payment cannot be added to this invoice."
        else:
            try:
                amount = Decimal(request.POST.get("amount", "0"))
                if amount <= 0:
                    raise ValueError("Payment amount must be greater than zero.")
                if amount != amount.quantize(Decimal("0.01")):
                    raise ValueError("Payment amount can have maximum 2 decimal places.")
            except (InvalidOperation, ValueError, TypeError):
                error = "Please enter a valid payment amount."

            if not error:
                payment_method = request.POST.get("payment_method", "CASH")
                valid_methods = dict(Payment.PAYMENT_METHOD_CHOICES)

                if payment_method not in valid_methods:
                    error = "Please select a valid payment method."

            if not error:
                payment_date_text = request.POST.get("payment_date", "")
                try:
                    payment_date = (
                        date.fromisoformat(payment_date_text)
                        if payment_date_text
                        else timezone.localdate()
                    )
                except ValueError:
                    error = "Please enter a valid payment date."

            if not error and amount > balance:
                error = "Payment cannot be greater than the remaining balance."

            if not error:
                with transaction.atomic():
                    locked_invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
                    current_paid = sum(
                        (p.amount for p in locked_invoice.payments.all()),
                        Decimal("0.00")
                    )
                    current_balance = locked_invoice.grand_total - current_paid

                    if amount > current_balance:
                        error = "Balance changed. Please refresh and try again."
                    else:
                        Payment.objects.create(
                            invoice=locked_invoice,
                            amount=amount,
                            payment_date=payment_date,
                            payment_method=payment_method,
                            reference=request.POST.get("reference", "").strip(),
                            notes=request.POST.get("notes", "").strip(),
                        )

                        new_paid = current_paid + amount
                        locked_invoice.status = (
                            "PAID" if new_paid >= locked_invoice.grand_total
                            else "PARTIAL"
                        )
                        locked_invoice.save(update_fields=["status", "updated_at"])

                if not error:
                    messages.success(request, "Payment recorded successfully.")
                    return redirect("invoice_payments", invoice_id=invoice_id)

    payment_history = invoice.payments.order_by("-payment_date", "-id")
    paid_amount = sum(
        (payment.amount for payment in payment_history),
        Decimal("0.00")
    )
    balance = invoice.grand_total - paid_amount

    return render(
        request,
        "accounts/invoice_payments.html",
        {
            "invoice": invoice,
            "payment_history": payment_history,
            "paid_amount": paid_amount,
            "balance": balance,
            "error": error,
        }
    )
