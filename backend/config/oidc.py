from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


def client_for_tsidp():
    from authlib.integrations.django_client import OAuth

    oauth = OAuth()
    if settings.TSIDP_ISSUER and settings.TSIDP_CLIENT_ID:
        oauth.register(
            name="tsidp",
            client_id=settings.TSIDP_CLIENT_ID,
            client_secret=settings.TSIDP_CLIENT_SECRET,
            server_metadata_url=f"{settings.TSIDP_ISSUER.rstrip('/')}/.well-known/openid-configuration",
            client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256"},
        )
    return oauth.create_client("tsidp")


def tsidp_login(request):
    client = client_for_tsidp()
    if client is None:
        return JsonResponse({"error": "tsidp is not configured; set TSIDP_ISSUER and TSIDP_CLIENT_ID."}, status=503)
    return client.authorize_redirect(request, request.build_absolute_uri(reverse("oidc_callback")))


def tsidp_callback(request):
    error = request.GET.get("error")
    if error:
        description = request.GET.get("error_description", "")
        message = f"Tailscale IDP rejected sign-in: {error}"
        if description:
            message = f"{message}: {description}"
        return HttpResponseForbidden(message, content_type="text/plain; charset=utf-8")

    client = client_for_tsidp()
    if client is None:
        return JsonResponse({"error": "tsidp is not configured."}, status=503)
    token = client.authorize_access_token(request)
    claims = token.get("userinfo") or client.parse_id_token(request, token)
    identity = claims.get("email") or claims.get("preferred_username") or claims.get("sub", "")
    if settings.ALLOWED_IDENTITY and identity.casefold() != settings.ALLOWED_IDENTITY.casefold():
        return HttpResponseForbidden("This identity is not allowed to use the study app.")
    User = get_user_model()
    username = claims.get("sub") or identity
    user, _ = User.objects.get_or_create(username=username, defaults={"email": claims.get("email", "")})
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect(settings.LOGIN_REDIRECT_URL)


def tsidp_logout(request):
    logout(request)
    return redirect("/")


class TailscaleIdentityRequired:
    public_prefixes = ("/oidc/", "/static/", "/admin/login/")
    public_paths = ("/api/health",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            not settings.TSIDP_ISSUER
            or request.path in self.public_paths
            or request.path.startswith(self.public_prefixes)
        ):
            return self.get_response(request)
        if request.user.is_authenticated:
            return self.get_response(request)
        if request.path.startswith("/api/"):
            return JsonResponse({"error": "authentication required"}, status=401)
        return redirect(f"/oidc/login/?next={request.path}")
