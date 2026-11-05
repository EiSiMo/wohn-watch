"""Connection diagnostics for Telegram, written to the log only.

The probes open plain TLS connections without the bot token, so they cannot
reach any chat. They measure the failure rate independently of user traffic,
which tells a network problem apart from a quiet day.
"""
import asyncio
import errno
import logging
import os
import socket
import ssl
import time

from telegram.ext import ContextTypes

from app import settings

logger = logging.getLogger("wohnwatch.net")

HOST = "api.telegram.org"
PORT = 443
ATTEMPTS_PER_ADDRESS = 5
TIMEOUT_SECONDS = 6
PAUSE_SECONDS = 0.2
# Above this the ClientHello needs two TCP segments, which is what triggered
# the resets on the Pi. See openssl.cnf.
LARGE_CLIENT_HELLO_BYTES = 1200
MAX_CHAIN = 6


def client_hello_size() -> int:
    """Size of the ClientHello this process would send. Needs no network."""
    context = ssl.create_default_context()
    outgoing = ssl.MemoryBIO()
    tls = context.wrap_bio(ssl.MemoryBIO(), outgoing, server_hostname=HOST)
    try:
        tls.do_handshake()
    except ssl.SSLWantReadError:
        pass
    return outgoing.pending


def log_tls_setup() -> None:
    size = client_hello_size()
    logger.info("tls setup: %s, OPENSSL_CONF=%s, client hello %d bytes",
                ssl.OPENSSL_VERSION, os.environ.get("OPENSSL_CONF"), size)
    if size > LARGE_CLIENT_HELLO_BYTES:
        logger.warning("client hello is %d bytes: post-quantum key share is active, "
                       "expect connection resets from Telegram", size)


def describe_error(exc: BaseException) -> str:
    """The whole cause chain on one line.

    httpx.ConnectError stringifies to nothing, so the reason only shows up
    further down the chain.
    """
    parts = []
    seen = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen and len(parts) < MAX_CHAIN:
        seen.add(id(current))
        parts.append(repr(current)[:120])
        current = current.__cause__ or current.__context__
    # Request URLs contain the token, so an error text must never carry it out.
    return " <- ".join(parts).replace(settings.TELEGRAM_BOT_TOKEN, "***")


def _attempt(family: int, address: tuple) -> dict:
    """One TCP connect plus TLS handshake, with the phase that failed."""
    result: dict = {"phase": "tcp"}
    start = time.monotonic()
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.settimeout(TIMEOUT_SECONDS)
        try:
            sock.connect(address)
            result["tcp_ms"] = (time.monotonic() - start) * 1000
            result["phase"] = "tls"
            start = time.monotonic()
            with ssl.create_default_context().wrap_socket(sock, server_hostname=HOST) as tls:
                result["tls_ms"] = (time.monotonic() - start) * 1000
                result["version"] = tls.version()
                result["phase"] = "done"
        except OSError as e:  # ssl.SSLError is an OSError too
            result["error"] = repr(e)[:80]
            result["errno"] = e.errno
    return result


def _average(results: list[dict], key: str) -> int:
    values = [r[key] for r in results if key in r]
    return round(sum(values) / len(values)) if values else 0


def _probe_address(family: int, address: tuple) -> None:
    results = []
    for i in range(ATTEMPTS_PER_ADDRESS):
        if i:
            time.sleep(PAUSE_SECONDS)
        result = _attempt(family, address)
        if result.get("errno") == errno.ENETUNREACH:
            # Normal for IPv6 inside the default Docker network.
            logger.debug("telegram probe %s: no route", address[0])
            return
        results.append(result)

    good = [r for r in results if r["phase"] == "done"]
    versions = sorted({r["version"] for r in good})
    line = (f"telegram probe {address[0]}: ok={len(good)}/{len(results)} "
            f"tcp={_average(results, 'tcp_ms')}ms tls={_average(good, 'tls_ms')}ms "
            f"version={','.join(versions) or '-'}")
    failures = [f"{r['phase']}:{r['error']}" for r in results if r["phase"] != "done"]
    if failures:
        logger.warning("%s failures=%s", line, failures)
    else:
        logger.info(line)


def run_probe() -> None:
    try:
        infos = socket.getaddrinfo(HOST, PORT, type=socket.SOCK_STREAM)
    except OSError as e:
        logger.warning("telegram probe: dns failed: %r", e)
        return
    for family, _, _, _, address in infos:
        _probe_address(family, address)


async def probe_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await asyncio.to_thread(run_probe)
