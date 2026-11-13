from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import DistributorProfile, OTPVerification


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdminPasswordRecoveryTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_recovery_test",
            email="admin.recovery@example.com",
            password="OldAdmin!Password8472",
        )
        self.admin_otp_url = reverse("admin_generate_otp")
        self.admin_reset_url = reverse("admin_forgot_password")

    def generate_admin_otp(self):
        response = self.client.post(
            self.admin_otp_url,
            {"email": self.admin.email},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        return OTPVerification.objects.get(email__iexact=self.admin.email)

    def test_admin_otp_is_generated_and_emailed(self):
        record = self.generate_admin_otp()

        self.assertEqual(len(record.otp_code), 6)
        self.assertEqual(mail.outbox[0].to, [self.admin.email])
        self.assertEqual(
            self.client.session.get("admin_otp_email"),
            self.admin.email,
        )

    def test_distributor_cannot_generate_admin_otp(self):
        distributor = User.objects.create_user(
            username="distributor_recovery_test",
            email="distributor.recovery@example.com",
            password="OldDistributor!8472",
        )
        DistributorProfile.objects.create(
            user=distributor,
            phone="9876543210",
        )

        response = self.client.post(
            self.admin_otp_url,
            {"email": distributor.email},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            OTPVerification.objects.filter(
                email__iexact=distributor.email
            ).exists()
        )
        self.assertNotIn("admin_otp_email", self.client.session)

    def test_admin_password_reset_success(self):
        record = self.generate_admin_otp()
        new_password = "Zebra!Cloud#7391"

        response = self.client.post(
            self.admin_reset_url,
            {
                "email": self.admin.email,
                "otp": record.otp_code,
                "new_password": new_password,
                "confirm_password": new_password,
            },
        )

        self.assertRedirects(response, reverse("admin_login"))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(new_password))
        self.assertFalse(
            OTPVerification.objects.filter(
                email__iexact=self.admin.email
            ).exists()
        )
        self.assertNotIn("admin_otp_email", self.client.session)

    def test_wrong_admin_otp_is_rejected(self):
        record = self.generate_admin_otp()

        response = self.client.post(
            self.admin_reset_url,
            {
                "email": self.admin.email,
                "otp": "000000" if record.otp_code != "000000" else "111111",
                "new_password": "Zebra!Cloud#7391",
                "confirm_password": "Zebra!Cloud#7391",
            },
        )

        self.assertContains(response, "Invalid OTP")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("OldAdmin!Password8472"))

    def test_expired_admin_otp_is_rejected(self):
        record = self.generate_admin_otp()
        record.created_at = timezone.now() - timedelta(minutes=6)
        record.save(update_fields=["created_at"])

        response = self.client.post(
            self.admin_reset_url,
            {
                "email": self.admin.email,
                "otp": record.otp_code,
                "new_password": "Zebra!Cloud#7391",
                "confirm_password": "Zebra!Cloud#7391",
            },
        )

        self.assertContains(response, "OTP has expired")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("OldAdmin!Password8472"))

    def test_distributor_cannot_reset_password_through_admin_route(self):
        distributor = User.objects.create_user(
            username="distributor_reset_test",
            email="distributor.reset@example.com",
            password="OldDistributor!8472",
        )
        DistributorProfile.objects.create(
            user=distributor,
            phone="9876543210",
        )
        OTPVerification.objects.create(
            email=distributor.email,
            otp_code="123456",
        )

        session = self.client.session
        session["admin_otp_email"] = distributor.email
        session.save()

        response = self.client.post(
            self.admin_reset_url,
            {
                "email": distributor.email,
                "otp": "123456",
                "new_password": "NewDistributor!8472",
                "confirm_password": "NewDistributor!8472",
            },
        )

        self.assertContains(response, "Admin account or OTP not found")
        distributor.refresh_from_db()
        self.assertTrue(
            distributor.check_password("OldDistributor!8472")
        )

    def test_existing_distributor_password_recovery_still_works(self):
        distributor = User.objects.create_user(
            username="distributor_existing_flow",
            email="distributor.existing@example.com",
            password="OldDistributor!8472",
        )
        DistributorProfile.objects.create(
            user=distributor,
            phone="9876543210",
        )

        self.client.post(
            reverse("generate_otp"),
            {"email": distributor.email},
        )

        record = OTPVerification.objects.get(email__iexact=distributor.email)
        new_password = "Falcon!River#6284"

        response = self.client.post(
            reverse("forgot_password"),
            {
                "email": distributor.email,
                "otp": record.otp_code,
                "new_password": new_password,
                "confirm_password": new_password,
            },
        )

        self.assertRedirects(response, reverse("distributor_login"))
        distributor.refresh_from_db()
        self.assertTrue(distributor.check_password(new_password))
