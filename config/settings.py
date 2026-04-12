import importlib.util
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HAS_DRF_SPECTACULAR = importlib.util.find_spec("drf_spectacular") is not None

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") in {"1", "true", "True"}
ALLOWED_HOSTS = [host for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "deliveryrecords",
]
if HAS_DRF_SPECTACULAR:
    INSTALLED_APPS.insert(-1, "drf_spectacular")

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "delivery_record"),
            "USER": os.environ.get("POSTGRES_USER", "delivery_record"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "delivery_record"),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    origin
    for origin in os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        "http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if origin
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "deliveryrecords.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "EXCEPTION_HANDLER": "deliveryrecords.exceptions.api_exception_handler",
}
if HAS_DRF_SPECTACULAR:
    REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"

if HAS_DRF_SPECTACULAR:
    SPECTACULAR_SETTINGS = {
        "TITLE": "CLEVER Delivery Record API",
        "DESCRIPTION": "Service-owned OpenAPI schema for service-delivery-record.",
        "VERSION": "1.0.0",
        "SERVE_INCLUDE_SCHEMA": False,
    }

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-local-jwt-secret-key-32chars")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "msa-server")
JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE", "msa-server")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ORGANIZATION_MASTER_BASE_URL = os.environ.get("ORGANIZATION_MASTER_BASE_URL", "http://organization-master-api:8000")
DRIVER_PROFILE_BASE_URL = os.environ.get("DRIVER_PROFILE_BASE_URL", "http://driver-profile-api:8000")
DISPATCH_REGISTRY_BASE_URL = os.environ.get("DISPATCH_REGISTRY_BASE_URL", "http://dispatch-registry-api:8000")
ATTENDANCE_REGISTRY_BASE_URL = os.environ.get("ATTENDANCE_REGISTRY_BASE_URL", "http://attendance-registry-api:8000")
