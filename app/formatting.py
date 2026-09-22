"""Rendering of user-facing values: match messages and filter labels.

The match message keeps lazyflat's format character for character — it went
through several rounds of tuning in web/notifications.py.
"""
import re
from urllib.parse import quote

from app import i18n
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


def _wbs_label(wbs: str, lang: str) -> str:
    w = (wbs or "").strip().lower()
    if w == "erforderlich":
        return i18n.t("WBS_REQUIRED", lang)
    if w in ("nicht erforderlich", "kein", "nein", "no", "ohne", "-", ""):
        return i18n.t("WBS_NOT_REQUIRED", lang)
    return wbs  # pass through unrecognised literals


# (decimal separator, thousands separator) per language.
_SEPARATORS = {"de": (",", "."), "en": (".", ",")}


def format_number(v, lang: str, decimals: int = 2, *, trim: bool = True, thousands: bool = False) -> str:
    """A number the locale-correct way: German uses a comma as the decimal
    separator and a dot for thousands, English the other way round. Trailing
    zeros are trimmed unless it's money."""
    if v is None:
        return "—"
    dec, thou = _SEPARATORS.get(lang, _SEPARATORS["en"])
    s = f"{v:,.{decimals}f}" if thousands else f"{v:.{decimals}f}"
    if trim and "." in s:
        s = s.rstrip("0").rstrip(".")
    # Swap the separators via a placeholder so the two passes can't collide.
    return s.replace(",", "\x00").replace(".", dec).replace("\x00", thou)


def format_money(v, lang: str) -> str:
    if v is None:
        return "—"
    return i18n.t("MONEY_FORMAT", lang, amount=format_number(v, lang, 2, trim=False, thousands=True))


def parse_number(text: str, lang: str) -> float:
    """Locale-aware inverse of format_number, for free-text user input (not
    scraped data — that's always German-formatted and goes through
    Flat._parse_german_float instead). Anything unparseable -> 0.0."""
    if not text:
        return 0.0
    clean = re.sub(r"[^\d,.]", "", str(text))
    dec, thou = _SEPARATORS.get(lang, _SEPARATORS["en"])
    clean = clean.replace(thou, "").replace(dec, ".")
    try:
        return float(clean)
    except ValueError:
        return 0.0


def render_match(flat: dict, lang: str = "de") -> tuple[str, str]:
    """Return (markdown, plain) for one match. The plain variant is the
    fallback when Telegram rejects the Markdown (unescaped _ * [ in an
    address would otherwise swallow the alert silently)."""
    address = (flat.get("address") or "").strip()
    line1, line2 = _address_lines(address)
    link = flat.get("link", "")
    rooms = flat.get("rooms")
    size = flat.get("size")
    sqm_price = flat.get("sqm_price")
    wbs_txt = _wbs_label(flat.get("wbs", ""), lang)
    gmaps = flat.get("address_link_gmaps") or _gmaps_url(address)

    rent_str = format_money(flat.get("total_rent"), lang)
    if sqm_price:
        rent_str += f" ({format_number(sqm_price, lang, 2, trim=False)} €/m²)"

    facts = (
        f"{i18n.t('MATCH_RENT_LABEL', lang)}{rent_str}\n"
        f"{i18n.t('MATCH_SIZE_LABEL', lang)}{format_number(size, lang) + ' m²' if size is not None else '—'}\n"
        f"{i18n.t('MATCH_ROOMS_LABEL', lang)}{format_number(rooms, lang, 1)}\n"
        f"{i18n.t('MATCH_WBS_LABEL', lang)}{wbs_txt}\n"
        f"{i18n.t('MATCH_PROVIDER_LABEL', lang)}{provider_label(flat.get('provider'))}\n"
    )

    plain = f"{line1}\n{line2}\n{facts}\n{gmaps}\nOriginal: {link}"

    # Telegram Markdown can't span link text across newlines, so emit two
    # separate links sharing one Google Maps URL — both lines render blue,
    # the two-line layout survives.
    addr_md = f"[{line1}]({gmaps})"
    if line2:
        addr_md += f"\n[{line2}]({gmaps})"
    markdown = f"{addr_md}\n{facts}\n[{i18n.t('MATCH_LINK_LABEL', lang)}]({link})"

    return markdown, plain


# -- filter labels ----------------------------------------------------------

def _num(x) -> str:
    return "%g" % x


def label_rooms(f: dict, lang: str = "de") -> str:
    lo, hi = f.get("rooms_min"), f.get("rooms_max")
    if lo is None and hi is None:
        return i18n.t("OPT_ANY", lang)
    if lo is not None and hi is not None:
        return i18n.t("LABEL_ROOMS_RANGE", lang, lo=format_number(lo, lang, 1), hi=format_number(hi, lang, 1))
    if lo is not None:
        return i18n.t("LABEL_ROOMS_FROM", lang, value=format_number(lo, lang, 1))
    return i18n.t("LABEL_ROOMS_TO", lang, value=format_number(hi, lang, 1))


def label_room_bound(f: dict, field: str, lang: str = "de") -> str:
    v = f.get(field)
    return i18n.t("OPT_ANY", lang) if v is None else format_number(v, lang, 1)


def label_rent(f: dict, lang: str = "de") -> str:
    v = f.get("max_rent")
    return i18n.t("OPT_ANY", lang) if v is None else i18n.t("LABEL_RENT_MAX", lang, value=int(v))


def label_size(f: dict, lang: str = "de") -> str:
    v = f.get("min_size")
    return i18n.t("OPT_ANY", lang) if v is None else i18n.t("LABEL_SIZE_MIN", lang, value=int(v))


def label_wbs(f: dict, lang: str = "de") -> str:
    """The root-menu button label — reuses the keyboard's own "nur mit/ohne
    WBS" wording, distinct from filter_summary's shorter "mit/ohne WBS"."""
    key = (f.get("wbs_required") or "").strip()
    if key == "yes":
        return i18n.t("WBS_OPT_YES", lang)
    if key == "no":
        return i18n.t("WBS_OPT_NO", lang)
    return i18n.t("OPT_ANY", lang)


def _csv_list(value) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def label_districts(f: dict, lang: str = "de") -> str:
    sel = _csv_list(f.get("districts"))
    if not sel:
        return i18n.t("LABEL_ALL", lang)
    if len(sel) == 1:
        return sel[0]
    return i18n.t("LABEL_SELECTED_N", lang, n=len(sel))


def label_providers(f: dict, lang: str = "de") -> str:
    sel = _csv_list(f.get("providers"))
    if not sel:
        return i18n.t("LABEL_ALL", lang)
    if len(sel) == 1:
        return provider_label(sel[0])
    return i18n.t("LABEL_SELECTED_N", lang, n=len(sel))


def filter_summary(f: dict | None, lang: str = "de") -> str:
    """One-line summary, e.g. `2–3.5 Zi · ≤ 1500 € · ≥ 60 m² · ohne WBS · 4 Bezirke`."""
    if not f:
        return "—"
    parts: list[str] = []
    if f.get("rooms_min") is not None or f.get("rooms_max") is not None:
        parts.append(f"{label_rooms(f, lang)} {i18n.t('UNIT_ROOMS_SUFFIX', lang)}")
    if f.get("max_rent"):
        parts.append(f"≤ {int(f['max_rent'])} €")
    if f.get("min_size"):
        parts.append(f"≥ {int(f['min_size'])} m²")
    if f.get("wbs_required") == "yes":
        parts.append(i18n.t("LABEL_WITH_WBS", lang))
    elif f.get("wbs_required") == "no":
        parts.append(i18n.t("LABEL_WITHOUT_WBS", lang))
    n_d = len(_csv_list(f.get("districts")))
    if n_d:
        unit = i18n.t("UNIT_DISTRICT_SINGULAR" if n_d == 1 else "UNIT_DISTRICT_PLURAL", lang)
        parts.append(f"{n_d} {unit}")
    n_p = len(_csv_list(f.get("providers")))
    if n_p and n_p < len(PROVIDER_KEYS):
        unit = i18n.t("UNIT_PROVIDER_SINGULAR" if n_p == 1 else "UNIT_PROVIDER_PLURAL", lang)
        parts.append(f"{n_p} {unit}")
    return " · ".join(parts) if parts else i18n.t("LABEL_NO_RESTRICTION", lang)


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
