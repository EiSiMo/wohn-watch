"""Test env must be set before app.settings is imported anywhere."""
import os
import tempfile

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("BERLIN_WOHNEN_USERNAME", "user")
os.environ.setdefault("BERLIN_WOHNEN_PASSWORD", "pass")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="wohnwatch-test-"))
