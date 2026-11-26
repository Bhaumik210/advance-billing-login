from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import DistributorProfile


def distributor_required(view_func):
    @login_required(login_url="distributor_login")
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        is_distributor = DistributorProfile.objects.filter(
            user=request.user
        ).exists()

        if not is_distributor:
            raise PermissionDenied(
                "Only distributors can access this page."
            )

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def admin_required(view_func):
    @login_required(login_url="admin_login")
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        is_distributor = DistributorProfile.objects.filter(
            user=request.user
        ).exists()

        if is_distributor or not request.user.is_superuser:
            raise PermissionDenied(
                "Only authorized administrators can access this page."
            )

        return view_func(request, *args, **kwargs)

    return _wrapped_view

