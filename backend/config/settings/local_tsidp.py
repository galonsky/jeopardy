from .local import *  # noqa: F403

if TSIDP_ISSUER and TSIDP_CLIENT_ID:  # noqa: F405
    MIDDLEWARE = [*MIDDLEWARE, "config.oidc.TailscaleIdentityRequired"]  # noqa: F405
