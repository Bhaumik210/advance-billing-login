from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Customer, DistributorProfile, Invoice, Payment


User = get_user_model()


class AdminReportsTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username="reports_admin",
            password="StrongPassword2026!",
            is_staff=True,
        )
        self.client.login(
            username="reports_admin",
            password="StrongPassword2026!",
        )

        self.customer = Customer.objects.create(
            name="Reports Test Customer",
            email="reports_customer@example.com",
            phone="9876543210",
            address="Test Address",
        )

        self.url = reverse("admin_reports")

    def create_invoice(self, number, amount, status):
        return Invoice.objects.create(
            invoice_number=number,
            customer=self.customer,
            subtotal=Decimal(amount),
            gst_amount=Decimal("0.00"),
            grand_total=Decimal(amount),
            status=status,
        )

    def test_partial_payment_calculation(self):
        invoice = self.create_invoice(
            "REPORT-PARTIAL-001", "1000.00", "PARTIAL"
        )
        Payment.objects.create(
            invoice=invoice,
            amount=Decimal("400.00"),
            payment_method="CASH",
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_sales"], Decimal("1000.00"))
        self.assertEqual(response.context["paid_amount"], Decimal("400.00"))
        self.assertEqual(response.context["pending_amount"], Decimal("600.00"))

    def test_full_payment_calculation(self):
        invoice = self.create_invoice(
            "REPORT-PAID-001", "1500.00", "PAID"
        )
        Payment.objects.create(
            invoice=invoice,
            amount=Decimal("1500.00"),
            payment_method="UPI",
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["paid_amount"], Decimal("1500.00"))
        self.assertEqual(response.context["pending_amount"], Decimal("0.00"))

    def test_draft_and_cancelled_invoices_excluded_from_sales(self):
        self.create_invoice("REPORT-UNPAID-001", "1000.00", "UNPAID")
        self.create_invoice("REPORT-DRAFT-001", "500.00", "DRAFT")
        self.create_invoice("REPORT-CANCEL-001", "700.00", "CANCELLED")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_sales"], Decimal("1000.00"))
        self.assertEqual(response.context["pending_amount"], Decimal("1000.00"))

    def test_non_staff_user_cannot_access_reports(self):
        self.client.logout()
        user = User.objects.create_user(
            username="reports_distributor",
            password="StrongPassword2026!",
        )
        DistributorProfile.objects.create(
            user=user,
            phone="9876543210",
        )
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_pdf_report_download(self):
        self.create_invoice("REPORT-PDF-001", "1200.00", "UNPAID")

        response = self.client.get(self.url, {"export": "pdf"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(b"%PDF", response.content[:10])
        self.assertIn("attachment", response["Content-Disposition"])
