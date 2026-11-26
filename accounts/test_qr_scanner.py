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
        self.profile = DistributorProfile.objects.create(
            user=self.user,
            phone="9876543210"
        )
        self.client.login(
            username="qr_test_user",
            password="StrongPassword2026!"
        )

        self.customer = Customer.objects.create(
            name="QR Test Customer",
            distributor=self.profile,
            email="qr_customer@example.com",
            phone="9876543210",
            address="Test Address"
        )

        self.invoice = Invoice.objects.create(
            invoice_number="QR-TEST-001",
            distributor=self.profile,
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



    def test_invoice_creation_generates_qr_image(self):
        from django.core.files.storage import default_storage
        from django.test import override_settings
        from io import BytesIO
        from unittest.mock import patch
        from PIL import Image
        from accounts.models import Product

        product = Product.objects.create(
            name="QR Test Product",
            category="Test",
            price=Decimal("100.00"),
            stock=10,
            gst_rate=Decimal("18.00"),
            distributor=self.profile,
        )

        url = reverse("create_invoice")

        with override_settings(MEDIA_ROOT="/tmp/qr_invoice_test_media"):
            response = self.client.post(
                url,
                {
                    "customer": str(self.customer.pk),
                    "product_id": [str(product.pk)],
                    "quantity": ["2"],
                    "discount_rate": ["0"],
                },
            )

            self.assertEqual(response.status_code, 302)

            invoice = Invoice.objects.exclude(
                pk=self.invoice.pk
            ).latest("pk")

            self.assertTrue(invoice.qr_code)
            self.assertTrue(default_storage.exists(invoice.qr_code.name))

            with invoice.qr_code.open("rb") as qr_file:
                image = Image.open(qr_file)
                self.assertEqual(image.format, "PNG")
                self.assertGreater(image.width, 0)
                self.assertGreater(image.height, 0)

            self.assertIn(
                f"created_invoice={invoice.pk}",
                response.url,
            )

            invoice.qr_code.delete(save=False)

    def test_oversized_qr_image_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        oversized_image = SimpleUploadedFile(
            "large_qr.png",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="image/png",
        )

        response = self.client.post(
            self.url,
            {"qr_image": oversized_image},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "QR image must be 5 MB or smaller.",
        )
