from decimal import Decimal
from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import F, Q
from django.db.models.functions import Lower


class OTPVerification(models.Model):

    email = models.EmailField()

    otp_code = models.CharField(
        max_length=6
    )

    purpose = models.CharField(
        max_length=32,
        choices=[
            ("distributor_reset", "Distributor Password Reset"),
            ("admin_reset", "Admin Password Reset"),
        ],
        default="distributor_reset",
        db_index=True,
    )

    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(
                fields=["email", "purpose"],
                name="accounts_ot_email_262f7f_idx",
            ),
        ]

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def is_expired(self):
        return (
            timezone.now()
            > self.created_at + timedelta(minutes=5)
        )

    def __str__(self):
        return self.email


class OTPResendLimit(models.Model):

    email = models.EmailField()

    purpose = models.CharField(
        max_length=32,
        choices=[
            ("distributor_reset", "Distributor Password Reset"),
            ("admin_reset", "Admin Password Reset"),
        ],
    )

    last_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    window_started_at = models.DateTimeField(
        default=timezone.now,
    )

    request_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["email", "purpose"],
                name="unique_otp_resend_limit",
            ),
        ]

    def __str__(self):
        return f"{self.email} - {self.purpose}"


class DistributorProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="distributor_profile"
    )

    phone = models.CharField(
        max_length=10
    )

    # Business Details
    business_name = models.CharField(
        max_length=150,
        blank=True
    )

    business_address = models.TextField(
        blank=True
    )

    gstin = models.CharField(
        max_length=15,
        blank=True
    )

    # Company Logo
    logo = models.ImageField(
        upload_to="company_logos/",
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.user.email


class Customer(models.Model):

    name = models.CharField(
        max_length=100
    )

    email = models.EmailField()

    phone = models.CharField(
        max_length=10
    )

    address = models.TextField()

    distributor = models.ForeignKey(
        DistributorProfile,
        on_delete=models.PROTECT,
        related_name="customers",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("email"), F("distributor"),
                name="uniq_customer_email_per_distributor_ci",
            ),
            models.UniqueConstraint(
                Lower("email"),
                condition=Q(distributor__isnull=True),
                name="uniq_legacy_customer_email_ci",
            ),
        ]

    def __str__(self):
        return self.name


class Product(models.Model):

    name = models.CharField(
        max_length=150
    )

    category = models.CharField(
        max_length=100
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    stock = models.PositiveIntegerField(
        default=0
    )

    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    description = models.TextField(
        blank=True
    )

    distributor = models.ForeignKey(
        DistributorProfile,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.name


# ============================================================
# INVOICE MODEL
# ============================================================

class Invoice(models.Model):

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("UNPAID", "Unpaid"),
        ("PARTIAL", "Partially Paid"),
        ("PAID", "Paid"),
        ("CANCELLED", "Cancelled"),
    ]

    invoice_number = models.CharField(
        max_length=30,
        unique=True
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="invoices"
    )

    distributor = models.ForeignKey(
        DistributorProfile,
        on_delete=models.PROTECT,
        related_name="invoices",
        null=True,
        blank=True,
    )

    invoice_date = models.DateField(
        default=timezone.localdate
    )

    # Total amount before discount
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    # Total discount applied to invoice items
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    # GST calculated after discount
    gst_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    # Final amount after discount and GST
    grand_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="DRAFT"
    )

    qr_code = models.ImageField(
        upload_to="invoice_qr/",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.invoice_number


class Payment(models.Model):

    PAYMENT_METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("UPI", "UPI"),
        ("CARD", "Card"),
        ("BANK", "Bank Transfer"),
        ("OTHER", "Other"),
    ]

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="payments",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    payment_date = models.DateField(
        default=timezone.localdate,
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="CASH",
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.amount}"


# ============================================================
# INVOICE ITEM MODEL
# ============================================================

class InvoiceItem(models.Model):

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="invoice_items"
    )

    quantity = models.PositiveIntegerField(
        default=1
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00")
    )

    # Discount percentage for this product
    discount_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00")
    )

    # Discount amount for this product
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    # Original subtotal before discount
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"