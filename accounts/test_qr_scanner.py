from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Customer, DistributorProfile, Invoice, Payment


User = get_user_model()


class QRScannerTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="qr_test_user",
            password="StrongPassword2026!"
        )
        DistributorProfile.objects.create(
            user=self.user,
            phone="9876543210"
        )
        self.client.login(
            username="qr_test_user",
            password="StrongPassword2026!"
        )

        self.customer = Customer.objects.create(
            name="QR Test Customer",
            email="qr_customer@example.com",
            phone="9876543210",
            address="Test Address"
        )

        self.invoice = Invoice.objects.create(
            invoice_number="QR-TEST-001",
            customer=self.customer,
            subtotal=Decimal("1000.00"),
            gst_amount=Decimal("180.00"),
            grand_total=Decimal("1180.00"),
            status="PARTIAL"
        )

        Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("500.00"),
            payment_method="CASH"
        )

        self.url = reverse("qr_scanner")

    def test_valid_qr_returns_invoice_details(self):
        response = self.client.post(
            self.url,
            {"qr_data": f"http://localhost:8000/invoices/{self.invoice.id}/"}
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(
            data["invoice"]["invoice_number"],
            "QR-TEST-001"
        )
        self.assertEqual(
            data["invoice"]["customer_name"],
            "QR Test Customer"
        )
        self.assertEqual(data["invoice"]["grand_total"], "1180.00")
        self.assertEqual(data["invoice"]["paid_amount"], "500.00")
        self.assertEqual(data["invoice"]["balance"], "680.00")

    def test_invalid_qr_url_returns_error(self):
        response = self.client.post(
            self.url,
            {"qr_data": "https://example.com/invalid-page/"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_nonexistent_invoice_returns_error(self):
        response = self.client.post(
            self.url,
            {"qr_data": "http://localhost:8000/invoices/999999/"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invoice not found", response.json()["error"])

    def test_login_required_for_qr_scanner(self):
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_admin_cannot_access_qr_scanner(self):
        admin_user = User.objects.create_user(
            username="qr_test_admin",
            password="StrongPassword2026!"
        )
        self.client.force_login(admin_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
