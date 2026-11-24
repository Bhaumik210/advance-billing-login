from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from accounts.models import DistributorProfile

User = get_user_model()


class DistributorProfileEditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="profileuser",
            email="old@example.com",
            password="StrongPass2026!",
            first_name="Old",
            last_name="Name",
        )
        self.profile = DistributorProfile.objects.create(
            user=self.user,
            phone="9876543210",
            business_name="Old Business",
        )
        self.url = reverse("edit_distributor_profile")
        self.client.force_login(self.user)

        self.data = {
            "name": "Test Distributor",
            "email": "new@example.com",
            "phone": "9123456789",
            "business_name": "New Business",
            "business_address": "Test Address",
            "gstin": "",
        }

    def test_profile_update_success(self):
        response = self.client.post(self.url, self.data)

        self.assertRedirects(
            response, reverse("distributor_profile")
        )

        self.user.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertEqual(self.user.first_name, "Test")
        self.assertEqual(self.user.last_name, "Distributor")
        self.assertEqual(self.user.email, "new@example.com")
        self.assertEqual(self.profile.phone, "9123456789")
        self.assertEqual(self.profile.business_name, "New Business")
        self.assertEqual(self.profile.business_address, "Test Address")

    def test_invalid_email_does_not_update_profile(self):
        response = self.client.post(
            self.url, {**self.data, "email": "invalid-email"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "valid email address")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "old@example.com")

    def test_invalid_phone_does_not_update_profile(self):
        response = self.client.post(
            self.url, {**self.data, "phone": "12345"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "exactly 10 digits")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.phone, "9876543210")

    def test_invalid_gstin_does_not_update_profile(self):
        response = self.client.post(
            self.url, {**self.data, "gstin": "INVALIDGSTIN"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "valid 15-character GSTIN")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.business_name, "Old Business")

    def test_duplicate_email_does_not_update_profile(self):
        User.objects.create_user(
            username="anotheruser",
            email="taken@example.com",
            password="StrongPass2026!",
        )

        response = self.client.post(
            self.url, {**self.data, "email": "taken@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already used")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "old@example.com")

    def test_login_required_for_profile_edit(self):
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("distributor_login"),
            response.url,
        )

    def test_business_name_over_150_characters_is_rejected(self):
        response = self.client.post(
            self.url,
            {**self.data, "business_name": "A" * 151}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Business name cannot exceed 150 characters.")
        self.user.refresh_from_db()
        self.assertEqual(self.profile.business_name, "Old Business")

    def test_admin_cannot_access_profile_edit(self):
        admin_user = User.objects.create_user(
            username="profile_test_admin",
            password="StrongPass2026!"
        )
        self.client.force_login(admin_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
