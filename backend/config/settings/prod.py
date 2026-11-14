from .base import *  # noqa: F403

if SECRET_KEY == "local-only-change-me":  # noqa: F405
    raise RuntimeError("SECRET_KEY must be configured in production")
if not TSIDP_ISSUER or not TSIDP_CLIENT_ID or not TSIDP_CLIENT_SECRET or not ALLOWED_IDENTITY:  # noqa: F405
    raise RuntimeError("TSIDP_ISSUER, TSIDP_CLIENT_ID, TSIDP_CLIENT_SECRET, and ALLOWED_IDENTITY must be set")
DEBUG = False
MIDDLEWARE = [*MIDDLEWARE, "config.oidc.TailscaleIdentityRequired"]  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
