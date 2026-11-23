from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from accounts.models import DistributorProfile


User = get_user_model()


class AdminLoginTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="admin_test",
            email="admin@example.com",
            password="StrongPass123"
        )

    def test_admin_login_with_valid_credentials(self):
        response = self.client.post(
            reverse("admin_login"),
            {"username": "admin_test", "password": "StrongPass123"}
        )
        self.assertRedirects(
            response, reverse("dashboard"), fetch_redirect_response=False
        )
        self.assertEqual(
            str(self.user.pk),
            self.client.session["_auth_user_id"]
        )

    def test_admin_login_rejects_wrong_password(self):
        response = self.client.post(
            reverse("admin_login"),
            {"username": "admin_test", "password": "WrongPass123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


    def test_admin_login_rejects_distributor_account(self):
        distributor = User.objects.create_user(
            username="wrong_distributor",
            email="wrong_distributor@example.com",
            password="StrongPass123"
        )
        DistributorProfile.objects.create(
            user=distributor,
            phone="9876543210"
        )
        response = self.client.post(
            reverse("admin_login"),
            {"username": "wrong_distributor", "password": "StrongPass123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)



class DistributorLoginTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="distributor_test",
            email="distributor@example.com",
            password="StrongPass123"
        )
        DistributorProfile.objects.create(
            user=self.user,
            phone="9876543210"
        )

    def test_distributor_login_with_username(self):
        response = self.client.post(
            reverse("distributor_login"),
            {"username": "distributor_test", "password": "StrongPass123"}
        )
        self.assertRedirects(
            response,
            reverse("distributor_profile"),
            fetch_redirect_response=False
        )
        self.assertEqual(
            str(self.user.pk),
            self.client.session["_auth_user_id"]
        )

    def test_distributor_login_with_email(self):
        response = self.client.post(
            reverse("distributor_login"),
            {"username": "distributor@example.com", "password": "StrongPass123"}
        )
        self.assertRedirects(
            response,
            reverse("distributor_profile"),
            fetch_redirect_response=False
        )
        self.assertEqual(
            str(self.user.pk),
            self.client.session["_auth_user_id"]
        )

    def test_distributor_login_rejects_wrong_password(self):
        response = self.client.post(
            reverse("distributor_login"),
            {"username": "distributor_test", "password": "WrongPass123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_distributor_login_rejects_admin_account(self):
        admin = User.objects.create_user(
            username="wrong_admin",
            email="wrong_admin@example.com",
            password="StrongPass123"
        )
        response = self.client.post(
            reverse("distributor_login"),
            {"username": "wrong_admin", "password": "StrongPass123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

class LogoutTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username="logout_admin",
            email="logout_admin@example.com",
            password="StrongPass123"
        )
        self.distributor = User.objects.create_user(
            username="logout_distributor",
            email="logout_distributor@example.com",
            password="StrongPass123"
        )
        DistributorProfile.objects.create(
            user=self.distributor,
            phone="9876543211"
        )

    def test_admin_logout(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("logout"))

        self.assertRedirects(
            response, reverse("admin_login"), fetch_redirect_response=False
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_distributor_logout(self):
        self.client.force_login(self.distributor)
        response = self.client.post(reverse("logout"))

        self.assertRedirects(
            response, reverse("distributor_login"), fetch_redirect_response=False
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_rejects_get_request(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("logout"))

        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
