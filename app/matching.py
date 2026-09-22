"""Per-chat filter matching.

Each chat has one row in chat_filters. A flat matches when all of that
chat's non-null constraints are satisfied. An empty filter matches everything.

Lifted from lazyflat's web/matching.py; the only addition is the Anbieter
criterion, which mirrors the Bezirk block exactly.
"""
from app.providers import UNKNOWN

# German labels per filter dimension, in stable display order.
_REASON_ORDER = ("Zimmer", "Preis", "Größe", "WBS", "Bezirk", "Anbieter")

# The scraper writes the literal label from inberlinwohnen.de. A census of all
# 365 live listings found three values: "erforderlich" (90), "nicht
# erforderlich" (271) and "unbekannt" (4). The short forms remain as a safety
# net in case the page wording changes.
_WBS_NOT_REQUIRED_LITERALS = ("nicht erforderlich", "kein", "nein", "no", "ohne", "-", "")
_WBS_REQUIRED_LITERALS = ("erforderlich", "ja", "yes", "wbs")


def _csv_set(value) -> set[str]:
    return {v.strip() for v in (value or "").split(",") if v.strip()}


def flat_filter_failures(flat: dict, f: dict | None) -> list[str]:
    """Return the German labels of the dimensions the flat fails. Empty = match.

    Each label appears at most once (rooms_min and rooms_max both map to
    "Zimmer"). Bezirk and Anbieter: an empty stored value means "no filter",
    so everything matches. When either filter is active, a flat whose
    Bezirk/Anbieter we could not determine counts as a failure — if someone
    bothered to narrow down, we shouldn't sneak in listings we couldn't place.
    """
    if not f:
        return []
    failures: set[str] = set()

    rooms = flat.get("rooms") or 0.0
    rent = flat.get("total_rent") or 0.0
    size = flat.get("size") or 0.0
    wbs_str = str(flat.get("wbs", "")).strip().lower()

    if f.get("rooms_min") is not None and rooms < float(f["rooms_min"]):
        failures.add("Zimmer")
    if f.get("rooms_max") is not None and rooms > float(f["rooms_max"]):
        failures.add("Zimmer")
    if f.get("max_rent") is not None and rent > float(f["max_rent"]):
        failures.add("Preis")
    if f.get("min_size") is not None and size < float(f["min_size"]):
        failures.add("Größe")

    # Three-way, because the portal really does publish "unbekannt". An
    # undetermined WBS status fails either direction, same rule as an
    # undetermined Bezirk or Anbieter.
    wbs_req = (f.get("wbs_required") or "").strip().lower()
    if wbs_req == "yes" and wbs_str not in _WBS_REQUIRED_LITERALS:
        failures.add("WBS")
    elif wbs_req == "no" and wbs_str not in _WBS_NOT_REQUIRED_LITERALS:
        failures.add("WBS")

    selected_districts = _csv_set(f.get("districts"))
    if selected_districts:
        flat_district = (flat.get("district") or "").strip()
        if not flat_district or flat_district not in selected_districts:
            failures.add("Bezirk")

    selected_providers = _csv_set(f.get("providers"))
    if selected_providers:
        flat_provider = (flat.get("provider") or "").strip()
        if not flat_provider or flat_provider == UNKNOWN or flat_provider not in selected_providers:
            failures.add("Anbieter")

    return [r for r in _REASON_ORDER if r in failures]


def flat_matches_filter(flat: dict, f: dict | None) -> bool:
    """f is a chat_filters row as a dict (or None = no filter set)."""
    return not flat_filter_failures(flat, f)


def row_to_dict(row) -> dict:
    if row is None:
        return {}
    try:
        return {k: row[k] for k in row.keys()}
    except Exception:
        return dict(row)
