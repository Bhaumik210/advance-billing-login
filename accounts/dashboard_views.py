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

from .decorators import admin_required, distributor_required

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


@admin_required
def dashboard(request):

    return render(
        request,
        "accounts/dashboard.html"
    )


@admin_required
def admin_reports(request):
    """Admin-only business reports with date filtering and CSV export."""
    import csv
    from datetime import date
    from decimal import Decimal
    from django.db.models import Sum, Count
    from django.http import HttpResponse


    invoices = Invoice.objects.select_related("customer").all().order_by("-invoice_date")

    date_filter_submitted = "start_date" in request.GET or "end_date" in request.GET

    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()
    parsed_start = None
    parsed_end = None
    date_error = ""

    if date_filter_submitted:
        if not start_date or not end_date:
            date_error = "Both start date and end date are required."
        else:
            try:
                parsed_start = date.fromisoformat(start_date)
                parsed_end = date.fromisoformat(end_date)

                if parsed_start > parsed_end:
                    date_error = "Start date cannot be later than end date."

            except ValueError:
                date_error = "Please enter valid dates."

    if not date_error:
        if parsed_start:
            invoices = invoices.filter(invoice_date__gte=parsed_start)
        if parsed_end:
            invoices = invoices.filter(invoice_date__lte=parsed_end)
    if request.GET.get("export") == "csv" and not date_error:
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="billing_reports.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "Invoice Number", "Customer", "Date",
            "Status", "Subtotal", "GST", "Grand Total"
        ])
        for invoice in invoices:
            writer.writerow([
                invoice.invoice_number,
                invoice.customer.name,
                invoice.invoice_date,
                invoice.status,
                invoice.subtotal,
                invoice.gst_amount,
                invoice.grand_total,
            ])
        return response

    active_invoices = invoices.exclude(status__in=["DRAFT", "CANCELLED"])

    total_sales = active_invoices.aggregate(
        total=Sum("grand_total")
    )["total"] or Decimal("0.00")

    paid_amount = Payment.objects.filter(
        invoice__in=active_invoices
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    pending_amount = total_sales - paid_amount

    gst_total = active_invoices.aggregate(
        total=Sum("gst_amount")
    )["total"] or Decimal("0.00")

    draft_amount = invoices.filter(status="DRAFT").aggregate(
        total=Sum("grand_total")
    )["total"] or Decimal("0.00")

    status_counts = {
        "PAID": invoices.filter(status="PAID").count(),
        "UNPAID": invoices.filter(status="UNPAID").count(),
        "DRAFT": invoices.filter(status="DRAFT").count(),
        "CANCELLED": invoices.filter(status="CANCELLED").count(),
    }

    daily_sales = active_invoices.values("invoice_date").annotate(
        total=Sum("grand_total"),
        invoice_count=Count("id")
    ).order_by("-invoice_date")[:15]

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "date_error": date_error,
        "total_invoices": invoices.count(),
        "total_sales": total_sales,
        "paid_amount": paid_amount,
        "pending_amount": pending_amount,
        "gst_total": gst_total,
        "draft_amount": draft_amount,
        "status_counts": status_counts,
        "total_customers": Customer.objects.count(),
        "total_products": Product.objects.count(),
        "low_stock_products": Product.objects.filter(stock__lte=5).count(),
        "daily_sales": daily_sales,
        "recent_invoices": invoices[:10],
    }

    if request.GET.get("export") == "pdf" and not date_error:
        from io import BytesIO
        from django.template.loader import render_to_string
        from xhtml2pdf import pisa

        pdf_html = render_to_string(
            "accounts/reports_pdf.html",
            {**context, "generated_on": timezone.localdate()},
        )
        pdf_buffer = BytesIO()
        pdf_result = pisa.CreatePDF(pdf_html, dest=pdf_buffer)

        if pdf_result.err:
            return HttpResponse("PDF generation failed.", status=500)

        response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="billing_reports.pdf"'
        return response

    return render(request, "accounts/reports.html", context)


@distributor_required
def qr_scanner(request):
    import re
    from decimal import Decimal
    from urllib.parse import urlsplit

    import cv2
    import numpy as np

    from django.db.models import Sum
    from django.http import JsonResponse
    from .models import Invoice

    context = {}

    def get_invoice_details(qr_value):
        parsed_url = urlsplit(qr_value.strip())
        match = re.fullmatch(r"/invoices/(\d+)/?", parsed_url.path)

        if not match:
            return None, "This QR code does not contain a valid invoice URL."

        try:
            invoice = Invoice.objects.select_related("customer").get(
                pk=int(match.group(1))
            )
        except (Invoice.DoesNotExist, ValueError):
            return None, "Invoice not found."

        paid_amount = invoice.payments.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        balance = invoice.grand_total - paid_amount

        details = {
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date.strftime("%d-%m-%Y"),
            "customer_name": invoice.customer.name,
            "subtotal": f"{invoice.subtotal:.2f}",
            "gst_amount": f"{invoice.gst_amount:.2f}",
            "grand_total": f"{invoice.grand_total:.2f}",
            "paid_amount": f"{paid_amount:.2f}",
            "balance": f"{balance:.2f}",
            "status": invoice.status,
        }

        return details, None

    if request.method == "POST":
        uploaded_file = request.FILES.get("qr_image")
        submitted_qr_data = request.POST.get("qr_data", "").strip()

        if submitted_qr_data:
            invoice_info, error = get_invoice_details(submitted_qr_data)

            if invoice_info:
                return JsonResponse({
                    "success": True,
                    "qr_data": submitted_qr_data,
                    "invoice": invoice_info,
                })

            return JsonResponse({
                "success": False,
                "error": error,
            }, status=400)

        if not uploaded_file:
            context["error"] = "Please upload a QR code image."
        else:
            try:
                image_bytes = uploaded_file.read()
                image_array = np.frombuffer(image_bytes, dtype=np.uint8)
                image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

                if image is None:
                    context["error"] = "Invalid image file."
                else:
                    detector = cv2.QRCodeDetector()
                    data, points, _ = detector.detectAndDecode(image)

                    if data:
                        context["qr_data"] = data
                        invoice_info, error = get_invoice_details(data)

                        if invoice_info:
                            context["invoice_info"] = invoice_info
                        else:
                            context["error"] = error
                    else:
                        context["error"] = (
                            "No QR code detected. Please try another image."
                        )

            except Exception:
                context["error"] = "Unable to scan this image."

    return render(request, "accounts/qr_scanner.html", context)
