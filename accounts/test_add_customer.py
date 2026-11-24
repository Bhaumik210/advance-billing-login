from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from accounts.models import Customer, DistributorProfile

User = get_user_model()


class AddCustomerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="customer_test_distributor",
            password="StrongPassword2026!"
        )
        DistributorProfile.objects.create(
            user=self.user,
            phone="9876543210"
        )
        self.client.force_login(self.user)

        self.url = reverse("add_customer")
        self.data = {
            "name": "Rahul Patel",
            "email": "rahul@example.com",
            "phone": "9876543210",
            "address": "Junagadh Gujarat"
        }

    def test_valid_customer_is_saved(self):
        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertTrue(
            Customer.objects.filter(email="rahul@example.com").exists()
        )
        self.assertContains(response, "Customer added successfully.")

    def test_duplicate_email_is_rejected(self):
        Customer.objects.create(**self.data)

        duplicate_data = self.data.copy()
        duplicate_data["email"] = "RAHUL@example.com"

        response = self.client.post(self.url, duplicate_data)

        self.assertEqual(Customer.objects.count(), 1)
        self.assertContains(response, "already exists")

    def test_invalid_email_is_rejected(self):
        data = self.data.copy()
        data["email"] = "invalid-email"

        response = self.client.post(self.url, data)

        self.assertEqual(Customer.objects.count(), 0)
        self.assertContains(response, "valid email")

    def test_invalid_phone_is_rejected(self):
        data = self.data.copy()
        data["phone"] = "12345"

        response = self.client.post(self.url, data)

        self.assertEqual(Customer.objects.count(), 0)
        self.assertContains(response, "exactly 10 digits")

    def test_short_name_is_rejected(self):
        data = self.data.copy()
        data["name"] = "A"

        response = self.client.post(self.url, data)

        self.assertEqual(Customer.objects.count(), 0)
        self.assertContains(response, "at least 2")

    def test_short_address_is_rejected(self):
        data = self.data.copy()
        data["address"] = "AB"

        response = self.client.post(self.url, data)

        self.assertEqual(Customer.objects.count(), 0)
        self.assertContains(response, "valid address")

    def test_empty_name_is_rejected(self):
        data = self.data.copy()
        data["name"] = ""
        response = self.client.post(self.url, data)
        self.assertEqual(Customer.objects.count(), 0)
        self.assertContains(response, "Customer name is required.")

    def test_empty_email_is_rejected(self):
        data = self.data.copy()
        data["email"] = ""
        response = self.client.post(self.url, data)
        self.assertEqual(Customer.objects.count(), 0)
        self.assertContains(response, "Email address is required.")

    def test_empty_phone_is_rejected(self):
        data = self.data.copy()
        data["phone"] = ""
        response = self.client.post(self.url, data)
        self.assertEqual(Customer.objects.count(), 0)
        self.assertContains(response, "Phone number is required.")

    def test_empty_address_is_rejected(self):
        data = self.data.copy()
        data["address"] = ""
        response = self.client.post(self.url, data)
        self.assertEqual(Customer.objects.count(), 0)
        self.assertContains(response, "Address is required.")

    def test_anonymous_user_cannot_add_customer(self):
        self.client.logout()

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("distributor_login"), response.url)
        self.assertEqual(Customer.objects.count(), 0)
