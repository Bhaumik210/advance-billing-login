from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache


@never_cache
@ensure_csrf_cookie
def admin_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect("dashboard")

        return render(
            request,
            "accounts/admin_login.html",
            {"error": "Invalid username or password"}
        )

    return render(request, "accounts/admin_login.html")


@never_cache
@ensure_csrf_cookie
def distributor_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect("dashboard")

        return render(
            request,
            "accounts/distributor_login.html",
            {"error": "Invalid username or password"}
        )

    return render(request, "accounts/distributor_login.html")


@login_required
def dashboard(request):
    return render(request, "accounts/dashboard.html")