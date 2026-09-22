from app.formatting import (
    _address_lines, _de, _de_money, filter_summary, render_match,
    selected_or_all, toggle_csv,
)
from app.berlin_districts import DISTRICTS
from app.providers import PROVIDER_KEYS

FLAT = {
    "address": "Beispielstr. 1, 10115, Mitte",
    "link": "https://www.gewobag.de/angebot/1",
    "rooms": 2.5, "size": 65.3, "total_rent": 1234.56, "sqm_price": 18.9060,
    "wbs": "nicht erforderlich", "provider": "gewobag.de",
}


def test_address_split():
    assert _address_lines("Str. 1, 10115, Mitte") == ("Str. 1", "10115 Mitte")
    assert _address_lines("Str. 1, Berlin") == ("Str. 1", "Berlin")
    assert _address_lines("Nur eine Zeile") == ("Nur eine Zeile", "")
    assert _address_lines("") == ("", "")


def test_match_message_shape():
    md, plain = render_match(FLAT)
    # Two separate links to the same Maps URL keep the two-line address clickable.
    assert md.count("google.com/maps") == 2
    assert "Miete: 1.234,56 € (18,91 €/m²)" in md
    assert "Anbieter: Gewobag" in md
    assert md.endswith("[Zur original Anzeige](https://www.gewobag.de/angebot/1)")
    assert "](" not in plain and FLAT["link"] in plain


def test_markdown_hostile_address_still_produces_a_plain_fallback():
    hostile = dict(FLAT, address="Kanzler_straße *17* [B], 10115, Mitte")
    md, plain = render_match(hostile)
    assert "Kanzler_straße *17* [B]" in plain
    assert md  # the fallback exists precisely because this one may be rejected


def test_missing_values_render_as_dash():
    md, _ = render_match({"address": "X", "link": "y"})
    assert "Miete: —" in md and "Zimmer: —" in md and "Fläche: —" in md


def test_german_number_formatting():
    assert _de(65.3) == "65,3"
    assert _de(55.50) == "55,5"
    assert _de(2.0) == "2"
    assert _de(2.5, 1) == "2,5"
    assert _de(18.906, 2, trim=False) == "18,91"
    assert _de(None) == "—"


def test_money_keeps_cents_and_groups_thousands():
    assert _de_money(1234.56) == "1.234,56 €"
    assert _de_money(676.5) == "676,50 €"
    assert _de_money(1200.0) == "1.200,00 €"
    assert _de_money(None) == "—"


def test_units_are_attached():
    md, _ = render_match({"address": "X", "link": "y", "size": 57.24, "rooms": 2.0,
                          "total_rent": 738.98})
    assert "Fläche: 57,24 m²" in md
    assert "Zimmer: 2\n" in md
    assert "Miete: 738,98 €" in md


def test_filter_summary():
    assert filter_summary(None) == "—"
    assert filter_summary({}) == "—"
    f = {"rooms_min": 2, "rooms_max": 3.5, "max_rent": 1500, "min_size": 60,
         "wbs_required": "no", "districts": "Mitte,Pankow", "providers": ""}
    assert filter_summary(f) == "2–3.5 Zi · ≤ 1500 € · ≥ 60 m² · ohne WBS · 2 Bezirke"


def test_filter_summary_open_ended_rooms():
    assert filter_summary({"rooms_min": 2}) == "ab 2 Zi"
    assert filter_summary({"rooms_max": 3}) == "bis 3 Zi"


def test_summary_hides_provider_filter_when_all_selected():
    f = {"providers": ",".join(PROVIDER_KEYS)}
    assert "Anbieter" not in filter_summary(f)


def test_empty_selection_renders_as_all():
    assert selected_or_all("", DISTRICTS) == set(DISTRICTS)
    assert selected_or_all("Mitte", DISTRICTS) == {"Mitte"}


def test_toggle_unticks_from_all_then_returns_to_all():
    after = toggle_csv("", DISTRICTS, "Mitte")
    assert "Mitte" not in after.split(",")
    assert len(after.split(",")) == len(DISTRICTS) - 1
    assert toggle_csv(after, DISTRICTS, "Mitte") == ""


def test_toggle_keeps_canonical_order():
    csv = toggle_csv("", DISTRICTS, DISTRICTS[5])
    names = csv.split(",")
    assert names == [d for d in DISTRICTS if d != DISTRICTS[5]]


def test_toggling_the_last_item_off_falls_back_to_no_filter():
    assert toggle_csv("Mitte", DISTRICTS, "Mitte") == ""
