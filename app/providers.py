"""The six Berlin housing associations behind inberlinwohnen.de.

inberlinwohnen.de is only the portal — its "alle Details" link points at the
landlord's own site, so the listing URL's domain identifies the provider.
Domains verified against lazyflat's apply/providers/*.py implementations.
"""
from urllib.parse import urlparse

UNKNOWN = "unbekannt"

# key (= domain) -> display name. Order defines button order.
PROVIDERS: dict[str, str] = {
    "gewobag.de": "Gewobag",
    "degewo.de": "degewo",
    "gesobau.de": "GESOBAU",
    "howoge.de": "HOWOGE",
    "stadtundland.de": "Stadt und Land",
    "wbm.de": "WBM",
}

PROVIDER_KEYS: list[str] = list(PROVIDERS)


def provider_for_link(link: str | None) -> str:
    """Map a listing URL to a provider key, or UNKNOWN.

    Matches on the registrable domain suffix so that regional subdomains
    (e.g. immo.gewobag.de) still resolve to their provider.
    """
    if not link:
        return UNKNOWN
    host = urlparse(link).netloc.lower().removeprefix("www.")
    if not host:
        return UNKNOWN
    if host in PROVIDERS:
        return host
    for key in PROVIDERS:
        if host.endswith("." + key):
            return key
    return UNKNOWN


def provider_label(key: str | None) -> str:
    """Display name for a provider key; unknown keys pass through."""
    if not key:
        return UNKNOWN
    return PROVIDERS.get(key, key)
