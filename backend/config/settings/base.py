from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR.parent / ".env")
SECRET_KEY = env("SECRET_KEY", default="local-only-change-me")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "testserver"])
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.pubsub.RedisPubSubChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    "address": env("REDIS_URL", default="redis://localhost:6379"),
                    "db": env.int("REDIS_DB_BASE", default=0) + 1,
                }
            ]
        },
    }
}
REDIS_DB_BASE = env.int("REDIS_DB_BASE", default=0)
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379")
TASKIQ_REDIS_URL = env("TASKIQ_REDIS_URL", default=REDIS_URL)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"db": REDIS_DB_BASE},
    }
}
REDIS_DB_BASE = env.int("REDIS_DB_BASE", default=0)
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379")
TASKIQ_REDIS_URL = env("TASKIQ_REDIS_URL", default=REDIS_URL)
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "core",
    "clues",
    "classification",
    "study",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"].setdefault("OPTIONS", {}).update(
        {
            "pool": {
                "min_size": env.int("DB_POOL_MIN_SIZE", default=4),
                "max_size": env.int("DB_POOL_MAX_SIZE", default=20),
            }
        }
    )
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR.parent / "frontend" / "dist"] if (BASE_DIR.parent / "frontend" / "dist").exists() else []
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
CLASSIFICATION_MODEL = env("CLASSIFICATION_MODEL", default="")
OPENAI_BASE_URL = env("OPENAI_BASE_URL", default="https://api.openai.com/v1")
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
TSIDP_ISSUER = env("TSIDP_ISSUER", default="")
TSIDP_CLIENT_ID = env("TSIDP_CLIENT_ID", default="")
TSIDP_CLIENT_SECRET = env("TSIDP_CLIENT_SECRET", default="")
ALLOWED_IDENTITY = env("ALLOWED_IDENTITY", default="")
LOGIN_URL = "/oidc/login/"
LOGIN_REDIRECT_URL = "/"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "rename_fields": {"levelname": "status"},
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
