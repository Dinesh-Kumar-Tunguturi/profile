from .settings import *

# Build-time overrides (no DB, no SMTP)
DEBUG = False
DATABASES = {"default": {"ENGINE": "django.db.backends.dummy"}}
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
