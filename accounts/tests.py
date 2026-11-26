from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from accounts.models import DistributorProfile
import json

User = get_user_model()


class AdminRegistrationTests(TestCase):
    def setUp(self):
        self.url = reverse("admin_register_api")
        self.data = {
            "full_name": "Test Admin",
            "username": "testadmin",
            "email": "admin_test@example.com",
            "password": "Strong!Admin2026#Qx",
            "confirm_password": "Strong!Admin2026#Qx",
        }

        self.admin = User.objects.create_superuser(
            username="authorized_admin",
            email="authorized@example.com",
            password="SecureAdmin2026!"
        )
        self.client.force_login(self.admin)

    def register(self, **overrides):
        data = {**self.data, **overrides}
        return self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_admin_registration_success(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="testadmin")
        self.assertTrue(user.check_password(self.data["password"]))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_anonymous_user_cannot_register_admin(self):
        self.client.logout()
        response = self.register()
        self.assertEqual(response.status_code, 403)

    def test_normal_user_cannot_register_admin(self):
        normal_user = User.objects.create_user(
            username="normaluser",
            password="NormalPass2026!"
        )
        self.client.force_login(normal_user)
        response = self.register()
        self.assertEqual(response.status_code, 403)
    def test_admin_registration_get_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_admin_registration_invalid_email(self):
        response = self.register(email="invalid-email")
        self.assertEqual(response.status_code, 400)

    def test_admin_registration_password_mismatch(self):
        response = self.register(confirm_password="DifferentPass2026!")
        self.assertEqual(response.status_code, 400)

    def test_admin_registration_duplicate_username(self):
        User.objects.create_user(
            username="testadmin",
            email="other@example.com",
            password="ExistingPass2026!",
        )
        response = self.register()
        self.assertEqual(response.status_code, 400)

    def test_admin_registration_duplicate_email(self):
        User.objects.create_user(
            username="anotheruser",
            email="admin_test@example.com",
            password="ExistingPass2026!",
        )
        response = self.register()
        self.assertEqual(response.status_code, 400)



    def test_admin_registration_weak_password(self):
        response = self.register(
            password="weakpass",
            confirm_password="weakpass",
        )
        self.assertEqual(response.status_code, 400)

    def test_admin_registration_missing_required_field(self):
        response = self.register(full_name="")
        self.assertEqual(response.status_code, 400)

    def test_admin_registration_invalid_username(self):
        response = self.register(username="invalid username!")
        self.assertEqual(response.status_code, 400)

class DistributorRegistrationTests(TestCase):
    def setUp(self):
        self.url = reverse("distributor_register")
        self.data = {
            "name": "Test Distributor",
            "email": "distributor_test@example.com",
            "phone": "9876543210",
            "password": "SecurePass2026",
        }

        self.admin = User.objects.create_superuser(
            username="authorized_admin",
            email="authorized@example.com",
            password="SecureAdmin2026!"
        )
        self.client.force_login(self.admin)

    def register(self, **overrides):
        data = {**self.data, **overrides}
        return self.client.post(self.url, data)

    def test_distributor_registration_success(self):
        response = self.register()
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="distributor_test@example.com")
        self.assertTrue(user.check_password(self.data["password"]))
        profile = DistributorProfile.objects.get(user=user)
        self.assertEqual(profile.phone, "9876543210")

    def test_distributor_registration_invalid_name(self):
        response = self.register(name="12345")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Full name should contain")

    def test_distributor_registration_invalid_email(self):
        response = self.register(email="invalid-email")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid email address")

    def test_distributor_registration_invalid_phone(self):
        response = self.register(phone="12345")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "exactly 10 digits")

    def test_distributor_registration_weak_password(self):
        response = self.register(password="weakpass")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "uppercase letter")

    def test_distributor_registration_duplicate_email(self):
        User.objects.create_user(
            username="existing@example.com",
            email="distributor_test@example.com",
            password="ExistingPass2026!",
        )
        response = self.register()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already registered")


