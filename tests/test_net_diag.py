"""Telegram diagnostics. No network: sockets are stubbed out."""
import errno
import logging
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from app import settings
from app.services import net_diag

REPO_ROOT = Path(__file__).resolve().parent.parent
ADDRESS = ("149.154.166.110", 443)
INFO = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ADDRESS)]


def _ok(*_):
    return {"phase": "done", "tcp_ms": 30.0, "tls_ms": 90.0, "version": "TLSv1.3"}


@pytest.fixture
def probed(monkeypatch, caplog):
    monkeypatch.setattr(net_diag.socket, "getaddrinfo", lambda *a, **k: INFO)
    monkeypatch.setattr(net_diag, "PAUSE_SECONDS", 0)
    caplog.set_level(logging.DEBUG, logger="wohnwatch.net")
    return caplog


def test_openssl_cnf_keeps_client_hello_in_one_segment():
    """The actual fix: the config has to shrink the hello in a real process."""
    env = {**os.environ, "OPENSSL_CONF": str(REPO_ROOT / "openssl.cnf")}
    out = subprocess.run(
        [sys.executable, "-c",
         "from app.services.net_diag import client_hello_size as c; print(c())"],
        env=env, cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    assert 0 < int(out.stdout) <= net_diag.LARGE_CLIENT_HELLO_BYTES


def test_large_client_hello_warns(monkeypatch, caplog):
    monkeypatch.setattr(net_diag, "client_hello_size", lambda: 1532)
    with caplog.at_level(logging.INFO, logger="wohnwatch.net"):
        net_diag.log_tls_setup()
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_describe_error_shows_the_buried_cause():
    root = ConnectionResetError(errno.ECONNRESET, "Connection reset by peer")
    try:
        try:
            raise root
        except OSError as e:
            raise RuntimeError("") from e
    except RuntimeError as outer:
        text = net_diag.describe_error(outer)
    assert "RuntimeError" in text
    assert "Connection reset by peer" in text


def test_describe_error_redacts_the_token():
    text = net_diag.describe_error(ValueError(f"/bot{settings.TELEGRAM_BOT_TOKEN}/send"))
    assert settings.TELEGRAM_BOT_TOKEN not in text


def test_probe_success_logs_info(probed, monkeypatch):
    monkeypatch.setattr(net_diag, "_attempt", _ok)
    net_diag.run_probe()
    assert "ok=5/5" in probed.text
    assert not [r for r in probed.records if r.levelno >= logging.WARNING]


def test_probe_failure_logs_phase_and_error(probed, monkeypatch):
    results = [_ok(), _ok(), _ok(), _ok(),
               {"phase": "tls", "tcp_ms": 30.0, "errno": errno.ECONNRESET,
                "error": "ConnectionResetError(104)"}]
    monkeypatch.setattr(net_diag, "_attempt", lambda *_: results.pop(0))
    net_diag.run_probe()
    warning = next(r for r in probed.records if r.levelno == logging.WARNING)
    assert "ok=4/5" in warning.getMessage()
    assert "tls:ConnectionResetError(104)" in warning.getMessage()


def test_probe_ignores_address_without_route(probed, monkeypatch):
    monkeypatch.setattr(net_diag, "_attempt", lambda *_: {
        "phase": "tcp", "errno": errno.ENETUNREACH, "error": "OSError(101)"})
    net_diag.run_probe()
    assert not [r for r in probed.records if r.levelno >= logging.INFO]


def test_probe_reports_dns_failure(probed, monkeypatch):
    def fail(*_, **__):
        raise socket.gaierror("no dns")
    monkeypatch.setattr(net_diag.socket, "getaddrinfo", fail)
    net_diag.run_probe()
    assert "dns failed" in probed.text
