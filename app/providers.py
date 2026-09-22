"""The Berlin housing associations behind inberlinwohnen.de.

inberlinwohnen.de is only the portal — its "alle Details" link points at the
landlord's own site, so the listing URL's domain identifies the provider.

Verified against a full census of all 365 live listings (2026-09-22): howoge
127, berlinovo 76, degewo 68, gewobag 57, stadtundland 19, gesobau 18, wbm 0.
Every single listing resolved to one of these, so UNKNOWN should stay empty in
practice — if it starts showing up, this list needs another domain.
"""
from urllib.parse import urlparse

UNKNOWN = "unbekannt"

# key (= domain) -> display name. Order defines button order.
PROVIDERS: dict[str, str] = {
    "howoge.de": "HOWOGE",
    "berlinovo.de": "berlinovo",
    "degewo.de": "degewo",
    "gewobag.de": "Gewobag",
    "stadtundland.de": "Stadt und Land",
    "gesobau.de": "GESOBAU",
    # No live listings during the census, but WBM is one of the associations
    # and does publish through the portal.
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
