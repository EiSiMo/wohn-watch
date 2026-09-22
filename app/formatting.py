"""Rendering of user-facing values: match messages and filter labels.

The match message keeps lazyflat's format character for character — it went
through several rounds of tuning in web/notifications.py.
"""
from urllib.parse import quote

from app.providers import PROVIDER_KEYS, provider_label


# -- match message ----------------------------------------------------------

def _address_lines(address: str) -> tuple[str, str]:
    """Split "Street Nr, PLZ, District" into (line1, line2). Degrades
    gracefully for unexpected shapes."""
    parts = [p.strip() for p in (address or "").split(",") if p.strip()]
    if len(parts) >= 3:
        return parts[0], f"{parts[1]} {', '.join(parts[2:])}"
    if len(parts) == 2:
        return parts[0], parts[1]
    return (address or "").strip(), ""


def _gmaps_url(address: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote(address or '')}"


def _wbs_label(wbs: str) -> str:
    w = (wbs or "").strip().lower()
    if w == "erforderlich":
        return "erforderlich"
    if w in ("nicht erforderlich", "kein", "nein", "no", "ohne", "-", ""):
        return "nicht erforderlich"
    return wbs  # pass through unrecognised literals


def _de(v, decimals: int = 2, *, trim: bool = True, thousands: bool = False) -> str:
    """A number the German way: comma as the decimal separator, optional dot
    as the thousands separator, trailing zeros trimmed unless it's money."""
    if v is None:
        return "—"
    s = f"{v:,.{decimals}f}" if thousands else f"{v:.{decimals}f}"
    if trim and "." in s:
        s = s.rstrip("0").rstrip(".")
    # Swap the separators via a placeholder so the two passes can't collide.
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _de_money(v) -> str:
    return "—" if v is None else _de(v, 2, trim=False, thousands=True) + " €"


def render_match(flat: dict) -> tuple[str, str]:
    """Return (markdown, plain) for one match. The plain variant is the
    fallback when Telegram rejects the Markdown (unescaped _ * [ in an
    address would otherwise swallow the alert silently)."""
    address = (flat.get("address") or "").strip()
    line1, line2 = _address_lines(address)
    link = flat.get("link", "")
    rooms = flat.get("rooms")
    size = flat.get("size")
    sqm_price = flat.get("sqm_price")
    wbs_txt = _wbs_label(flat.get("wbs", ""))
    gmaps = flat.get("address_link_gmaps") or _gmaps_url(address)

    rent_str = _de_money(flat.get("total_rent"))
    if sqm_price:
        rent_str += f" ({_de(sqm_price, 2, trim=False)} €/m²)"

    facts = (
        f"Miete: {rent_str}\n"
        f"Fläche: {_de(size) + ' m²' if size is not None else '—'}\n"
        f"Zimmer: {_de(rooms, 1)}\n"
        f"WBS: {wbs_txt}\n"
        f"Anbieter: {provider_label(flat.get('provider'))}\n"
    )

    plain = f"{line1}\n{line2}\n{facts}\n{gmaps}\nOriginal: {link}"

    # Telegram Markdown can't span link text across newlines, so emit two
    # separate links sharing one Google Maps URL — both lines render blue,
    # the two-line layout survives.
    addr_md = f"[{line1}]({gmaps})"
    if line2:
        addr_md += f"\n[{line2}]({gmaps})"
    markdown = f"{addr_md}\n{facts}\n[Zur original Anzeige]({link})"

    return markdown, plain


# -- filter labels ----------------------------------------------------------

def _num(x) -> str:
    return "%g" % x


def label_rooms(f: dict) -> str:
    lo, hi = f.get("rooms_min"), f.get("rooms_max")
    if lo is None and hi is None:
        return "egal"
    if lo is not None and hi is not None:
        return f"{_de(lo, 1)}–{_de(hi, 1)}"
    if lo is not None:
        return f"ab {_de(lo, 1)}"
    return f"bis {_de(hi, 1)}"


def label_room_bound(f: dict, field: str) -> str:
    v = f.get(field)
    return "egal" if v is None else _de(v, 1)


def label_rent(f: dict) -> str:
    v = f.get("max_rent")
    return "egal" if v is None else f"max. {int(v)} €"


def label_size(f: dict) -> str:
    v = f.get("min_size")
    return "egal" if v is None else f"ab {int(v)} m²"


def label_wbs(f: dict) -> str:
    return {"yes": "nur mit WBS", "no": "nur ohne WBS"}.get(
        (f.get("wbs_required") or "").strip(), "egal"
    )


def _csv_list(value) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def label_districts(f: dict) -> str:
    sel = _csv_list(f.get("districts"))
    if not sel:
        return "alle"
    if len(sel) == 1:
        return sel[0]
    return f"{len(sel)} ausgewählt"


def label_providers(f: dict) -> str:
    sel = _csv_list(f.get("providers"))
    if not sel:
        return "alle"
    if len(sel) == 1:
        return provider_label(sel[0])
    return f"{len(sel)} ausgewählt"


def filter_summary(f: dict | None) -> str:
    """One-line summary, e.g. `2–3.5 Zi · ≤ 1500 € · ≥ 60 m² · ohne WBS · 4 Bezirke`."""
    if not f:
        return "—"
    parts: list[str] = []
    if f.get("rooms_min") is not None or f.get("rooms_max") is not None:
        parts.append(f"{label_rooms(f)} Zi")
    if f.get("max_rent"):
        parts.append(f"≤ {int(f['max_rent'])} €")
    if f.get("min_size"):
        parts.append(f"≥ {int(f['min_size'])} m²")
    if f.get("wbs_required") == "yes":
        parts.append("mit WBS")
    elif f.get("wbs_required") == "no":
        parts.append("ohne WBS")
    n_d = len(_csv_list(f.get("districts")))
    if n_d:
        parts.append(f"{n_d} Bezirk{'e' if n_d != 1 else ''}")
    n_p = len(_csv_list(f.get("providers")))
    if n_p and n_p < len(PROVIDER_KEYS):
        parts.append(f"{n_p} Anbieter")
    return " · ".join(parts) if parts else "keine Einschränkung"


def selected_or_all(csv: str | None, all_items) -> set[str]:
    """What the multi-select keyboards should tick.

    An empty stored value means "no filter", which for the user reads as
    "all of them" — so render every item ticked. Unticking one then stores
    the explicit remainder.
    """
    sel = set(_csv_list(csv))
    return sel or set(all_items)


def toggle_csv(csv: str | None, all_items, item: str) -> str:
    """Flip one item and canonicalise.

    Both "everything selected" and "nothing selected" collapse to "" = filter
    off — the same rule lazyflat used, and it keeps the user from accidentally
    building a filter that can never match.
    """
    sel = selected_or_all(csv, all_items)
    sel.symmetric_difference_update({item})
    if not sel or sel == set(all_items):
        return ""
    return ",".join(i for i in all_items if i in sel)
