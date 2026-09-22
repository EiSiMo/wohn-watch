import pytest

from app.berlin_districts import DISTRICTS
from app.matching import flat_filter_failures, flat_matches_filter

FLAT = {
    "rooms": 2.5, "total_rent": 1200.0, "size": 60.0,
    "wbs": "nicht erforderlich", "district": "Mitte", "provider": "gewobag.de",
}


def test_empty_filter_matches_everything():
    assert flat_matches_filter(FLAT, {}) is True
    assert flat_matches_filter(FLAT, None) is True


@pytest.mark.parametrize("f,expected", [
    ({"rooms_min": 3}, ["Zimmer"]),
    ({"rooms_max": 2}, ["Zimmer"]),
    ({"rooms_min": 2, "rooms_max": 3}, []),
    ({"max_rent": 1000}, ["Preis"]),
    ({"max_rent": 1200}, []),
    ({"min_size": 70}, ["Größe"]),
    ({"min_size": 60}, []),
])
def test_numeric_criteria(f, expected):
    assert flat_filter_failures(FLAT, f) == expected


def test_rooms_min_and_max_collapse_to_one_label():
    assert flat_filter_failures(FLAT, {"rooms_min": 3, "rooms_max": 1}) == ["Zimmer"]


def test_wbs():
    assert flat_filter_failures(FLAT, {"wbs_required": "no"}) == []
    assert flat_filter_failures(FLAT, {"wbs_required": "yes"}) == ["WBS"]
    with_wbs = dict(FLAT, wbs="erforderlich")
    assert flat_filter_failures(with_wbs, {"wbs_required": "no"}) == ["WBS"]
    assert flat_filter_failures(with_wbs, {"wbs_required": "yes"}) == []


def test_wbs_empty_counts_as_not_required():
    blank = dict(FLAT, wbs="")
    assert flat_filter_failures(blank, {"wbs_required": "no"}) == []
    assert flat_filter_failures(blank, {"wbs_required": "yes"}) == ["WBS"]


def test_districts():
    assert flat_filter_failures(FLAT, {"districts": ""}) == []
    assert flat_filter_failures(FLAT, {"districts": "Mitte,Pankow"}) == []
    assert flat_filter_failures(FLAT, {"districts": "Spandau"}) == ["Bezirk"]


def test_unknown_district_excluded_when_filter_active():
    unknown = dict(FLAT, district=None)
    assert flat_filter_failures(unknown, {"districts": ""}) == []
    assert flat_filter_failures(unknown, {"districts": "Mitte"}) == ["Bezirk"]


def test_providers():
    assert flat_filter_failures(FLAT, {"providers": ""}) == []
    assert flat_filter_failures(FLAT, {"providers": "gewobag.de,wbm.de"}) == []
    assert flat_filter_failures(FLAT, {"providers": "wbm.de"}) == ["Anbieter"]


def test_unknown_provider_excluded_when_filter_active():
    unknown = dict(FLAT, provider="unbekannt")
    assert flat_filter_failures(unknown, {"providers": ""}) == []
    assert flat_filter_failures(unknown, {"providers": "wbm.de"}) == ["Anbieter"]


def test_missing_values_coerce_to_zero():
    empty = {}
    assert flat_filter_failures(empty, {"rooms_min": 1}) == ["Zimmer"]
    assert flat_filter_failures(empty, {"rooms_max": 1}) == []
    assert flat_filter_failures(empty, {"max_rent": 100}) == []
    assert flat_filter_failures(empty, {"min_size": 10}) == ["Größe"]


def test_failures_are_ordered_and_unique():
    f = {"rooms_min": 9, "max_rent": 1, "min_size": 999,
         "wbs_required": "yes", "districts": "Spandau", "providers": "wbm.de"}
    assert flat_filter_failures(FLAT, f) == [
        "Zimmer", "Preis", "Größe", "WBS", "Bezirk", "Anbieter"
    ]


def test_every_district_name_is_matchable():
    for d in DISTRICTS:
        assert flat_filter_failures(dict(FLAT, district=d), {"districts": d}) == []
