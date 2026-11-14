from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from config.oidc import TailscaleIdentityRequired, tsidp_callback


class TailscaleIdentityMiddlewareTests(SimpleTestCase):
    @override_settings(TSIDP_ISSUER="https://idp.example")
    def test_health_endpoint_is_public_for_kubernetes_probes(self):
        request = RequestFactory().get("/api/health")
        response = TailscaleIdentityRequired(lambda _: HttpResponse("ok"))(request)

        self.assertEqual(response.status_code, 200)

    @override_settings(TSIDP_ISSUER="https://idp.example")
    def test_other_api_endpoints_still_require_authentication(self):
        request = RequestFactory().get("/api/dashboard")
        request.user = AnonymousUser()
        response = TailscaleIdentityRequired(lambda _: HttpResponse("ok"))(request)

        self.assertEqual(response.status_code, 401)

    def test_callback_displays_identity_provider_denials(self):
        request = RequestFactory().get(
            "/oidc/callback/",
            {"error": "access_denied", "error_description": "tagged node lacks a user identity"},
        )
        response = tsidp_callback(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"tagged node lacks a user identity", response.content)
