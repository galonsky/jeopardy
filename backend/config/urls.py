from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView

from config.api import api
from config.oidc import tsidp_callback, tsidp_login, tsidp_logout


def spa(request):
    return TemplateView.as_view(template_name="index.html")(request)


spa = ensure_csrf_cookie(spa)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("oidc/login/", tsidp_login, name="oidc_login"),
    path("oidc/callback/", tsidp_callback, name="oidc_callback"),
    path("oidc/logout/", tsidp_logout, name="oidc_logout"),
    path("", spa, name="spa"),
]
