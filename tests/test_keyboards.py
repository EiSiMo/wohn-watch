from app import keyboards
from app.berlin_districts import DISTRICTS
from app.providers import PROVIDER_KEYS


def test_district_order_is_pinned():
    """Keyboards address Bezirke by index to fit callback_data into 64 bytes,
    which makes this order load-bearing: reordering it would silently remap
    every in-flight keyboard."""
    assert DISTRICTS == [
        "Mitte",
        "Friedrichshain-Kreuzberg",
        "Pankow",
        "Charlottenburg-Wilmersdorf",
        "Spandau",
        "Steglitz-Zehlendorf",
        "Tempelhof-Schöneberg",
        "Neukölln",
        "Treptow-Köpenick",
        "Marzahn-Hellersdorf",
        "Lichtenberg",
        "Reinickendorf",
    ]


def test_every_callback_payload_fits_telegrams_limit():
    for data in keyboards.all_callback_data():
        assert len(data.encode("utf-8")) <= keyboards.CB_LIMIT, data


def test_all_screens_render():
    f = {"rooms_min": 2.0, "rooms_max": 3.0, "max_rent": 1200.0, "min_size": 60.0,
         "wbs_required": "no", "districts": "Mitte", "providers": "wbm.de"}
    for screen in keyboards.WIZARD_SCREENS:
        for wizard in (False, True):
            text, markup = keyboards.render_screen(screen, f, wizard=wizard)
            assert text and markup.inline_keyboard


def test_wizard_shows_progress_and_menu_does_not():
    f = {}
    wizard_text, _ = keyboards.render_screen("rent", f, wizard=True)
    menu_text, _ = keyboards.render_screen("rent", f, wizard=False)
    assert "Schritt 3 von 7" in wizard_text
    assert "Schritt" not in menu_text


def test_first_wizard_screen_has_no_back_button():
    _, markup = keyboards.render_screen(keyboards.WIZARD_SCREENS[0], {}, wizard=True)
    nav = markup.inline_keyboard[-1]
    assert [b.callback_data for b in nav] == ["w:next"]


def test_root_menu_exposes_every_criterion():
    _, markup = keyboards.render_root({})
    data = [b.callback_data for row in markup.inline_keyboard for b in row]
    for screen in keyboards.WIZARD_SCREENS:
        assert f"m:{screen}" in data


def test_room_bounds_are_separate_screens_with_few_buttons():
    """Min and max used to share one screen, which meant 18 buttons at once."""
    assert "rmin" in keyboards.WIZARD_SCREENS and "rmax" in keyboards.WIZARD_SCREENS
    for screen in ("rmin", "rmax"):
        _, markup = keyboards.render_screen(screen, {})
        buttons = [b for row in markup.inline_keyboard for b in row]
        assert len(buttons) <= 12


def test_room_buttons_use_german_decimals():
    _, markup = keyboards.render_screen("rmin", {}, "de")
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert "1,5" in labels and "1.5" not in labels


def test_room_buttons_use_english_decimals():
    _, markup = keyboards.render_screen("rmin", {}, "en")
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert "1.5" in labels and "1,5" not in labels


def test_wizard_shows_progress_in_english():
    text, _ = keyboards.render_screen("rent", {}, "en", wizard=True)
    assert "Step 3 of 7" in text


def test_multi_select_marks_current_selection():
    _, markup = keyboards.render_screen("prov", {"providers": "wbm.de"})
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert any(l.startswith("✓ ") and "WBM" in l for l in labels)
    assert sum(1 for l in labels if l.startswith("✓ ")) == 1


def test_empty_multi_select_marks_all():
    _, markup = keyboards.render_screen("dist", {"districts": ""})
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert sum(1 for l in labels if l.startswith("✓ ")) == len(DISTRICTS)


def test_ask_fields_cover_every_numeric_input():
    assert set(keyboards.ASK_FIELDS.values()) == set(keyboards.INPUT_RANGES)


def test_provider_keys_all_have_buttons():
    _, markup = keyboards.render_screen("prov", {})
    data = [b.callback_data for row in markup.inline_keyboard for b in row]
    for key in PROVIDER_KEYS:
        assert f"tog:p:{key}" in data


def test_language_picker_has_a_button_per_supported_language():
    from app import i18n

    markup = keyboards.render_language_picker()
    data = [b.callback_data for row in markup.inline_keyboard for b in row]
    for code in i18n.SUPPORTED_LANGUAGES:
        assert f"lang:{code}" in data
