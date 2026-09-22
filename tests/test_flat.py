from app.flat import Flat

parse = Flat._parse_german_float


def test_german_decimals():
    assert parse("1.234,56 €") == 1234.56
    assert parse("2,5") == 2.5
    assert parse("65,3 m²") == 65.3
    assert parse("1.000") == 1000.0


def test_unparseable_is_zero():
    for bad in ("", None, "auf Anfrage", "—", "k.A."):
        assert parse(bad) == 0.0


def test_mapping_and_derived_fields():
    f = Flat({
        "id": "4711",
        "link": "https://www.gewobag.de/angebot/1",
        "Adresse": "Beispielstr. 1, 10115, Mitte",
        "Zimmeranzahl": "2,5",
        "Wohnfläche": "50 m²",
        "Gesamtmiete": "1.000,00 €",
        "WBS": "nicht erforderlich",
    })
    assert f.id == "https://www.gewobag.de/angebot/1"
    assert f.source_id == "4711"
    assert f.rooms == 2.5
    assert f.sqm_price == 20.0
    assert f.district == "Mitte"
    assert f.provider == "gewobag.de"


def test_zero_size_does_not_divide_by_zero():
    assert Flat({"Gesamtmiete": "900"}).sqm_price == 0.0


def test_payload_has_every_db_column():
    from app.db import _FLAT_COLS

    payload = Flat({"link": "https://wbm.de/x"}).to_payload()
    assert set(_FLAT_COLS) <= set(payload)
