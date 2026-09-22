"""Inline keyboards and the callback_data codec.

Telegram caps callback_data at 64 bytes, so Bezirke are addressed by their
*index* in berlin_districts.DISTRICTS ("Charlottenburg-Wilmersdorf" alone is
26 bytes). That makes the order of that list load-bearing — tests/test_keyboards.py
pins it.

The same screens serve both the guided setup and the /filter menu; `wizard`
only adds the progress line and a "Weiter" button.

Every render function takes `lang` and renders its labels via app.i18n.t().
`lang` defaults to "de" purely to limit churn in callers/tests that don't
care about language (mirrors the existing `wizard: bool = False` default) —
every real call site still passes it explicitly.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app import formatting, i18n
from app.berlin_districts import DISTRICTS
from app.providers import PROVIDERS, PROVIDER_KEYS

CB_LIMIT = 64

# Screens in the order the guided setup walks them. Min and max rooms are
# separate steps on purpose — one combined screen meant 18 buttons at once.
WIZARD_SCREENS = ("rmin", "rmax", "rent", "size", "wbs", "dist", "prov")
WIZARD_TOTAL = len(WIZARD_SCREENS)

ROOM_PRESETS = (1, 1.5, 2, 2.5, 3, 3.5, 4, 5)
RENT_PRESETS = (600, 800, 1000, 1200, 1500, 2000)
SIZE_PRESETS = (40, 50, 60, 70, 80)

# Sanity bounds for free-text input, so a typo can't silently mute the filter.
INPUT_RANGES = {
    "rooms_min": (0.5, 20.0),
    "rooms_max": (0.5, 20.0),
    "max_rent": (100.0, 10000.0),
    "min_size": (10.0, 500.0),
}

# callback key -> filter column, for the free-text prompts.
ASK_FIELDS = {
    "rmin": "rooms_min",
    "rmax": "rooms_max",
    "rent": "max_rent",
    "size": "min_size",
}

ANY = "-"  # "egal" sentinel inside callback_data


def cb(*parts) -> str:
    data = ":".join(str(p) for p in parts)
    assert len(data.encode("utf-8")) <= CB_LIMIT, f"callback_data too long: {data}"
    return data


def _num(v) -> str:
    """The value as it travels inside callback_data — always a dot, because
    the other side does float()."""
    return "%g" % v


def _label(v, lang: str) -> str:
    """The value as the user sees it on a button, locale-formatted."""
    return formatting.format_number(v, lang, 1)


def _btn(label: str, *data) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=cb(*data))


def _marked(label: str, active: bool) -> str:
    return f"✓ {label}" if active else label


def _chunk(items: list, per_row: int) -> list[list]:
    return [items[i:i + per_row] for i in range(0, len(items), per_row)]


def _nav(screen: str, wizard: bool, lang: str) -> list[list[InlineKeyboardButton]]:
    """Bottom row(s): wizard advances, menu goes back to root."""
    if not wizard:
        return [[_btn(i18n.t("NAV_BACK", lang), "m", "root")]]
    idx = WIZARD_SCREENS.index(screen)
    row = []
    if idx > 0:
        row.append(_btn(i18n.t("NAV_BACK", lang), "w", "back"))
    row.append(_btn(i18n.t("NAV_NEXT", lang), "w", "next"))
    return [row]


# -- individual screens -----------------------------------------------------

def _room_bound_rows(f: dict, key: str, lang: str) -> list[list[InlineKeyboardButton]]:
    current = f.get(ASK_FIELDS[key])
    any_label = _marked(i18n.t("OPT_ANY", lang), current is None)
    buttons = [_btn(any_label, "set", key, ANY)]
    buttons += [
        _btn(_marked(_label(v, lang), current == v), "set", key, _num(v))
        for v in ROOM_PRESETS
    ]
    rows = _chunk(buttons, 3)
    rows.append([_btn(i18n.t("CUSTOM_VALUE", lang), "ask", key)])
    return rows


def _preset_rows(f: dict, field: str, key: str, presets, fmt, lang: str) -> list[list[InlineKeyboardButton]]:
    current = f.get(field)
    any_label = _marked(i18n.t("OPT_ANY", lang), current is None)
    buttons = [_btn(any_label, "set", key, ANY)]
    buttons += [
        _btn(_marked(fmt(v), current == v), "set", key, _num(v))
        for v in presets
    ]
    rows = _chunk(buttons, 4)
    rows.append([_btn(i18n.t("CUSTOM_VALUE", lang), "ask", key)])
    return rows


def _wbs_rows(f: dict, lang: str) -> list[list[InlineKeyboardButton]]:
    current = (f.get("wbs_required") or "").strip()
    options = (
        ("", i18n.t("OPT_ANY", lang)),
        ("no", i18n.t("WBS_OPT_NO", lang)),
        ("yes", i18n.t("WBS_OPT_YES", lang)),
    )
    return [
        [_btn(_marked(label, current == value), "set", "wbs", value or ANY)]
        for value, label in options
    ]


def _district_rows(f: dict, lang: str) -> list[list[InlineKeyboardButton]]:
    selected = formatting.selected_or_all(f.get("districts"), DISTRICTS)
    buttons = [
        _btn(f"{'✓ ' if name in selected else '· '}{name}", "tog", "d", i)
        for i, name in enumerate(DISTRICTS)
    ]
    rows = _chunk(buttons, 2)
    rows.append([_btn(i18n.t("SELECT_ALL", lang), "all", "d")])
    return rows


def _provider_rows(f: dict, lang: str) -> list[list[InlineKeyboardButton]]:
    selected = formatting.selected_or_all(f.get("providers"), PROVIDER_KEYS)
    buttons = [
        _btn(f"{'✓ ' if key in selected else '· '}{PROVIDERS[key]}", "tog", "p", key)
        for key in PROVIDER_KEYS
    ]
    rows = _chunk(buttons, 2)
    rows.append([_btn(i18n.t("SELECT_ALL", lang), "all", "p")])
    return rows


_SCREEN_QUESTION_KEYS = {
    "rmin": "Q_ROOMS_MIN",
    "rmax": "Q_ROOMS_MAX",
    "rent": "Q_RENT",
    "size": "Q_SIZE",
    "wbs": "Q_WBS",
    "dist": "Q_DISTRICTS",
    "prov": "Q_PROVIDERS",
}


def _screen_rows(screen: str, f: dict, lang: str) -> list[list[InlineKeyboardButton]]:
    if screen in ("rmin", "rmax"):
        return _room_bound_rows(f, screen, lang)
    if screen == "rent":
        return _preset_rows(f, "max_rent", "rent", RENT_PRESETS, lambda v: f"{int(v)} €", lang)
    if screen == "size":
        return _preset_rows(f, "min_size", "size", SIZE_PRESETS, lambda v: f"{int(v)} m²", lang)
    if screen == "wbs":
        return _wbs_rows(f, lang)
    if screen == "dist":
        return _district_rows(f, lang)
    if screen == "prov":
        return _provider_rows(f, lang)
    raise ValueError(f"unknown screen {screen!r}")


# -- public rendering -------------------------------------------------------

def render_root(f: dict, lang: str = "de") -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        [_btn(i18n.t("ROOT_ROOMS_MIN", lang, value=formatting.label_room_bound(f, "rooms_min", lang)), "m", "rmin")],
        [_btn(i18n.t("ROOT_ROOMS_MAX", lang, value=formatting.label_room_bound(f, "rooms_max", lang)), "m", "rmax")],
        [_btn(i18n.t("ROOT_RENT", lang, value=formatting.label_rent(f, lang)), "m", "rent")],
        [_btn(i18n.t("ROOT_SIZE", lang, value=formatting.label_size(f, lang)), "m", "size")],
        [_btn(i18n.t("ROOT_WBS", lang, value=formatting.label_wbs(f, lang)), "m", "wbs")],
        [_btn(i18n.t("ROOT_DISTRICTS", lang, value=formatting.label_districts(f, lang)), "m", "dist")],
        [_btn(i18n.t("ROOT_PROVIDERS", lang, value=formatting.label_providers(f, lang)), "m", "prov")],
        [_btn(i18n.t("RESET_FILTER", lang), "f", "clear")],
        [_btn(i18n.t("DONE", lang), "f", "done")],
    ]
    return i18n.t("MENU_TITLE", lang, summary=formatting.filter_summary(f, lang)), InlineKeyboardMarkup(rows)


def render_screen(screen: str, f: dict, lang: str = "de", wizard: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    rows = _screen_rows(screen, f, lang) + _nav(screen, wizard, lang)
    question = i18n.t(_SCREEN_QUESTION_KEYS[screen], lang)
    if wizard:
        text = i18n.t(
            "WIZARD_STEP", lang,
            n=WIZARD_SCREENS.index(screen) + 1, total=WIZARD_TOTAL, question=question,
        )
    else:
        text = question
    return text, InlineKeyboardMarkup(rows)


def render_confirm(f: dict, lang: str = "de") -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        [_btn(f"✅ {i18n.t('ACTIVATE_ALARMS', lang)}", "f", "activate")],
        [_btn(i18n.t("EDIT_AGAIN", lang), "m", "root")],
    ]
    return i18n.t("SUMMARY_CONFIRM", lang, summary=formatting.filter_summary(f, lang)), InlineKeyboardMarkup(rows)


def render_intro(lang: str = "de") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn(i18n.t("SETUP_FILTER", lang), "w", "start")],
        [_btn(i18n.t("JUST_LOOKING", lang), "f", "help")],
    ])


def render_delete_confirm(lang: str = "de") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        _btn(i18n.t("CONFIRM_DELETE_YES", lang), "del", "yes"),
        _btn(i18n.t("CANCEL", lang), "del", "no"),
    ]])


def render_language_picker(lang: str = "de") -> InlineKeyboardMarkup:
    """Buttons come straight from the supported-languages table, so a third
    language only needs an entry in app.i18n.LANGUAGE_NAMES."""
    return InlineKeyboardMarkup([
        [_btn(name, "lang", code)] for code, name in i18n.LANGUAGE_NAMES.items()
    ])


def all_callback_data() -> list[str]:
    """Every callback_data the bot can emit — used by the size test. Language
    is fixed ("de") since this only inspects callback_data, never label text."""
    f = {
        "rooms_min": 2.0, "rooms_max": 3.0, "max_rent": 1200.0, "min_size": 60.0,
        "wbs_required": "no", "districts": ",".join(DISTRICTS),
        "providers": ",".join(PROVIDER_KEYS),
    }
    markups = [
        render_root(f)[1], render_confirm(f)[1], render_intro(), render_delete_confirm(),
        render_language_picker(),
    ]
    markups += [render_screen(s, f, wizard=w)[1]
                for s in WIZARD_SCREENS for w in (False, True)]
    return [
        b.callback_data
        for m in markups for row in m.inline_keyboard for b in row
        if b.callback_data
    ]
