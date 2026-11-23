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
from django.contrib.auth.decorators import login_required
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


@login_required(
    login_url="distributor_login"
)
def add_product(request):

    error = None

    form_data = {
        "name": "",
        "category": "",
        "price": "",
        "stock": "",
        "gst_rate": "",
        "description": ""
    }

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        category = request.POST.get(
            "category",
            ""
        ).strip()

        price_value = request.POST.get(
            "price",
            ""
        ).strip()

        stock_value = request.POST.get(
            "stock",
            ""
        ).strip()

        gst_value = request.POST.get(
            "gst_rate",
            ""
        ).strip()

        description = request.POST.get(
            "description",
            ""
        ).strip()

        form_data = {
            "name": name,
            "category": category,
            "price": price_value,
            "stock": stock_value,
            "gst_rate": gst_value,
            "description": description
        }

        price = None
        stock = None
        gst_rate = None

        if not name:

            error = (
                "Product name is required."
            )

        elif len(name) < 2:

            error = (
                "Product name must contain "
                "at least 2 characters."
            )

        elif not category:

            error = (
                "Category is required."
            )

        if error is None:

            if not price_value:

                error = (
                    "Price is required."
                )

            else:

                try:

                    price = Decimal(
                        price_value
                    )

                    if price <= 0:

                        error = (
                            "Price must be greater than 0."
                        )

                except InvalidOperation:

                    error = (
                        "Enter a valid price."
                    )

        if error is None:

            if stock_value == "":

                error = (
                    "Stock is required."
                )

            else:

                try:

                    stock = int(
                        stock_value
                    )

                    if stock < 0:

                        error = (
                            "Stock cannot be negative."
                        )

                except ValueError:

                    error = (
                        "Stock must be a whole number."
                    )

        if error is None:

            if not gst_value:

                error = (
                    "GST rate is required."
                )

            else:

                try:

                    gst_rate = Decimal(
                        gst_value
                    )

                    if gst_rate < 0:

                        error = (
                            "GST rate cannot be negative."
                        )

                    elif gst_rate > 100:

                        error = (
                            "GST rate cannot be greater than 100."
                        )

                except InvalidOperation:

                    error = (
                        "Enter a valid GST rate."
                    )

        if error is None:

            Product.objects.create(
                name=name,
                category=category,
                price=price,
                stock=stock,
                gst_rate=gst_rate,
                description=description
            )

            messages.success(
                request,
                "Product added successfully."
            )

            return redirect(
                "add_product"
            )

    return render(
        request,
        "accounts/add_product.html",
        {
            "error": error,
            "form_data": form_data
        }
    )


@login_required(
    login_url="distributor_login"
)
def product_list(request):

    search_query = request.GET.get(
        "search",
        ""
    ).strip()

    products = Product.objects.all()

    if search_query:

        products = products.filter(
            Q(name__icontains=search_query)
            |
            Q(category__icontains=search_query)
            |
            Q(description__icontains=search_query)
        )

    products = products.order_by(
        "-created_at"
    )

    paginator = Paginator(
        products,
        5
    )

    page_number = request.GET.get(
        "page"
    )

    page_obj = paginator.get_page(
        page_number
    )

    return render(
        request,
        "accounts/product_list.html",
        {
            "page_obj": page_obj,
            "search_query": search_query
        }
    )


@login_required(
    login_url="distributor_login"
)
def delete_product(
    request,
    product_id
):

    if request.method != "POST":
        return redirect("product_list")

    product = get_object_or_404(
        Product,
        id=product_id
    )

    product_name = product.name

    try:

        product.delete()

        messages.success(
            request,
            f"Product '{product_name}' deleted successfully."
        )

    except ProtectedError:

        messages.error(
            request,
            f"Cannot delete '{product_name}' because it is already used in an invoice."
        )

    return redirect(
        "product_list"
    )


@login_required(
    login_url="distributor_login"
)
def edit_product(
    request,
    product_id
):

    product = get_object_or_404(
        Product,
        id=product_id
    )

    error = None

    form_data = {
        "name": product.name,
        "category": product.category,
        "price": product.price,
        "stock": product.stock,
        "gst_rate": product.gst_rate,
        "description": product.description
    }

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        category = request.POST.get(
            "category",
            ""
        ).strip()

        price_value = request.POST.get(
            "price",
            ""
        ).strip()

        stock_value = request.POST.get(
            "stock",
            ""
        ).strip()

        gst_value = request.POST.get(
            "gst_rate",
            ""
        ).strip()

        description = request.POST.get(
            "description",
            ""
        ).strip()

        form_data = {
            "name": name,
            "category": category,
            "price": price_value,
            "stock": stock_value,
            "gst_rate": gst_value,
            "description": description
        }

        price = None
        stock = None
        gst_rate = None

        if not name:

            error = (
                "Product name is required."
            )

        elif len(name) < 2:

            error = (
                "Product name must contain "
                "at least 2 characters."
            )

        elif not category:

            error = (
                "Category is required."
            )

        if error is None:

            if not price_value:

                error = (
                    "Price is required."
                )

            else:

                try:

                    price = Decimal(
                        price_value
                    )

                    if not price.is_finite():

                        error = (
                            "Enter a valid price."
                        )

                    elif price <= 0:

                        error = (
                            "Price must be greater than 0."
                        )

                except InvalidOperation:

                    error = (
                        "Enter a valid price."
                    )

        if error is None:

            if stock_value == "":

                error = (
                    "Stock is required."
                )

            else:

                try:

                    stock = int(
                        stock_value
                    )

                    if stock < 0:

                        error = (
                            "Stock cannot be negative."
                        )

                except ValueError:

                    error = (
                        "Stock must be a whole number."
                    )

        if error is None:

            if not gst_value:

                error = (
                    "GST rate is required."
                )

            else:

                try:

                    gst_rate = Decimal(
                        gst_value
                    )

                    if not gst_rate.is_finite():

                        error = (
                            "Enter a valid GST rate."
                        )

                    elif gst_rate < 0:

                        error = (
                            "GST rate cannot be negative."
                        )

                    elif gst_rate > 100:

                        error = (
                            "GST rate cannot be greater than 100."
                        )

                except InvalidOperation:

                    error = (
                        "Enter a valid GST rate."
                    )

        if error is None:

            product.name = name
            product.category = category
            product.price = price
            product.stock = stock
            product.gst_rate = gst_rate
            product.description = description

            product.save()

            messages.success(
                request,
                f"Product '{product.name}' updated successfully."
            )

            return redirect(
                "product_list"
            )

    return render(
        request,
        "accounts/edit_product.html",
        {
            "product": product,
            "form_data": form_data,
            "error": error
        }
    )
