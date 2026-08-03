"""
Shared pytest setup for the backend test suite.

Two jobs, both of which have to happen before any `from app...` import:

1. Put `backend/` on sys.path so `app` is importable when pytest is run from
   anywhere.
2. Make `app.config.Settings` constructible without a .env file. Importing
   anything under `app.services` pulls in app/services/__init__.py ->
   AuthService -> Settings, which has ten required fields and would otherwise
   raise ValidationError at import time on a machine with no .env.

The stubs are only injected when there is no .env to read, so a normal dev
checkout keeps using its real configuration and nothing here can shadow it.
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Settings fields with no default. Kept in sync with app/config.py by hand;
# a new required field there will surface here as a ValidationError on import.
_REQUIRED_SETTINGS = {
    "DATABASE_URL": "sqlite:///test.db",
    "AUTH0_DOMAIN": "test.auth0.com",
    "AUTH0_CLIENT_ID": "test-client-id",
    "AUTH0_CLIENT_SECRET": "test-client-secret",
    "AUTH0_AUDIENCE": "https://test.api",
    "AUTH0_MANAGEMENT_API_AUDIENCE": "https://test.auth0.com/api/v2/",
    "AUTH0_MANAGEMENT_CLIENT_ID": "test-mgmt-client-id",
    "AUTH0_MANAGEMENT_CLIENT_SECRET": "test-mgmt-client-secret",
    "SECRET_KEY": "test-secret-key",
    "ANTHROPIC_API_KEY": "sk-ant-test",
}

if not os.path.exists(os.path.join(BACKEND_DIR, ".env")):
    for _key, _value in _REQUIRED_SETTINGS.items():
        os.environ.setdefault(_key, _value)
