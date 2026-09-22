"""Inline keyboards and the callback_data codec.

Telegram caps callback_data at 64 bytes, so Bezirke are addressed by their
*index* in berlin_districts.DISTRICTS ("Charlottenburg-Wilmersdorf" alone is
26 bytes). That makes the order of that list load-bearing — tests/test_keyboards.py
pins it.

The same screens serve both the guided setup and the /filter menu; `wizard`
only adds the progress line and a "Weiter" button.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app import formatting, texts
from app.berlin_districts import DISTRICTS
from app.providers import PROVIDERS, PROVIDER_KEYS

CB_LIMIT = 64

# Screens in the order the guided setup walks them.
WIZARD_SCREENS = ("rooms", "rent", "size", "wbs", "dist", "prov")
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
    return "%g" % v


def _btn(label: str, *data) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=cb(*data))


def _chunk(items: list, per_row: int) -> list[list]:
    return [items[i:i + per_row] for i in range(0, len(items), per_row)]


def _nav(screen: str, wizard: bool) -> list[list[InlineKeyboardButton]]:
    """Bottom row(s): wizard advances, menu goes back to root."""
    if not wizard:
        return [[_btn("‹ Zurück", "m", "root")]]
    idx = WIZARD_SCREENS.index(screen)
    row = []
    if idx > 0:
        row.append(_btn("‹ Zurück", "w", "back"))
    row.append(_btn("Weiter ›", "w", "next"))
    return [row]


# -- individual screens -----------------------------------------------------

def _rooms_rows(f: dict) -> list[list[InlineKeyboardButton]]:
    lo, hi = f.get("rooms_min"), f.get("rooms_max")
    rows = []
    for key, current in (("rmin", lo), ("rmax", hi)):
        buttons = [
            _btn("✓ egal" if current is None else "egal", "set", key, ANY)
        ]
        buttons += [
            _btn(f"✓ {_num(v)}" if current == v else _num(v), "set", key, _num(v))
            for v in ROOM_PRESETS
        ]
        rows += _chunk(buttons, 5)
    rows.append([
        _btn("Min. eingeben", "ask", "rmin"),
        _btn("Max. eingeben", "ask", "rmax"),
    ])
    return rows


def _preset_rows(f: dict, field: str, key: str, presets, fmt) -> list[list[InlineKeyboardButton]]:
    current = f.get(field)
    buttons = [_btn("✓ egal" if current is None else "egal", "set", key, ANY)]
    buttons += [
        _btn(f"✓ {fmt(v)}" if current == v else fmt(v), "set", key, _num(v))
        for v in presets
    ]
    rows = _chunk(buttons, 4)
    rows.append([_btn("Eigener Wert", "ask", key)])
    return rows


def _wbs_rows(f: dict) -> list[list[InlineKeyboardButton]]:
    current = (f.get("wbs_required") or "").strip()
    options = (("", "egal"), ("no", "nur ohne WBS"), ("yes", "nur mit WBS"))
    return [
        [_btn(f"✓ {label}" if current == value else label, "set", "wbs", value or ANY)]
        for value, label in options
    ]


def _district_rows(f: dict) -> list[list[InlineKeyboardButton]]:
    selected = formatting.selected_or_all(f.get("districts"), DISTRICTS)
    buttons = [
        _btn(f"{'✓ ' if name in selected else '· '}{name}", "tog", "d", i)
        for i, name in enumerate(DISTRICTS)
    ]
    rows = _chunk(buttons, 2)
    rows.append([_btn("Alle auswählen", "all", "d")])
    return rows


def _provider_rows(f: dict) -> list[list[InlineKeyboardButton]]:
    selected = formatting.selected_or_all(f.get("providers"), PROVIDER_KEYS)
    buttons = [
        _btn(f"{'✓ ' if key in selected else '· '}{PROVIDERS[key]}", "tog", "p", key)
        for key in PROVIDER_KEYS
    ]
    rows = _chunk(buttons, 2)
    rows.append([_btn("Alle auswählen", "all", "p")])
    return rows


_SCREEN_QUESTIONS = {
    "rooms": texts.Q_ROOMS_MIN + "\n" + texts.Q_ROOMS_MAX,
    "rent": texts.Q_RENT,
    "size": texts.Q_SIZE,
    "wbs": texts.Q_WBS,
    "dist": texts.Q_DISTRICTS,
    "prov": texts.Q_PROVIDERS,
}


def _screen_rows(screen: str, f: dict) -> list[list[InlineKeyboardButton]]:
    if screen == "rooms":
        return _rooms_rows(f)
    if screen == "rent":
        return _preset_rows(f, "max_rent", "rent", RENT_PRESETS, lambda v: f"{int(v)} €")
    if screen == "size":
        return _preset_rows(f, "min_size", "size", SIZE_PRESETS, lambda v: f"{int(v)} m²")
    if screen == "wbs":
        return _wbs_rows(f)
    if screen == "dist":
        return _district_rows(f)
    if screen == "prov":
        return _provider_rows(f)
    raise ValueError(f"unknown screen {screen!r}")


# -- public rendering -------------------------------------------------------

def render_root(f: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        [_btn(f"Zimmer: {formatting.label_rooms(f)}", "m", "rooms")],
        [_btn(f"Miete: {formatting.label_rent(f)}", "m", "rent")],
        [_btn(f"Größe: {formatting.label_size(f)}", "m", "size")],
        [_btn(f"WBS: {formatting.label_wbs(f)}", "m", "wbs")],
        [_btn(f"Bezirke: {formatting.label_districts(f)}", "m", "dist")],
        [_btn(f"Anbieter: {formatting.label_providers(f)}", "m", "prov")],
        [_btn("Filter zurücksetzen", "f", "clear")],
        [_btn("Fertig", "f", "done")],
    ]
    return texts.MENU_TITLE.format(summary=formatting.filter_summary(f)), InlineKeyboardMarkup(rows)


def render_screen(screen: str, f: dict, wizard: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    rows = _screen_rows(screen, f) + _nav(screen, wizard)
    question = _SCREEN_QUESTIONS[screen]
    if wizard:
        text = texts.WIZARD_STEP.format(
            n=WIZARD_SCREENS.index(screen) + 1, total=WIZARD_TOTAL, question=question
        )
    else:
        text = question
    return text, InlineKeyboardMarkup(rows)


def render_confirm(f: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        [_btn("✅ Alarme aktivieren", "f", "activate")],
        [_btn("Nochmal bearbeiten", "m", "root")],
    ]
    return texts.SUMMARY_CONFIRM.format(summary=formatting.filter_summary(f)), InlineKeyboardMarkup(rows)


def render_intro() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("Filter einrichten", "w", "start")],
        [_btn("Erstmal nur gucken", "f", "help")],
    ])


def render_delete_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        _btn("Ja, alles löschen", "del", "yes"),
        _btn("Abbrechen", "del", "no"),
    ]])


def all_callback_data() -> list[str]:
    """Every callback_data the bot can emit — used by the size test."""
    f = {
        "rooms_min": 2.0, "rooms_max": 3.0, "max_rent": 1200.0, "min_size": 60.0,
        "wbs_required": "no", "districts": ",".join(DISTRICTS),
        "providers": ",".join(PROVIDER_KEYS),
    }
    markups = [render_root(f)[1], render_confirm(f)[1], render_intro(), render_delete_confirm()]
    markups += [render_screen(s, f, wizard=w)[1]
                for s in WIZARD_SCREENS for w in (False, True)]
    return [
        b.callback_data
        for m in markups for row in m.inline_keyboard for b in row
        if b.callback_data
    ]
