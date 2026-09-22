"""Parser tests against the markup shape the public Wohnungsfinder serves."""
from app.flat import Flat
from app.scraper import Scraper

# Trimmed from the live page: each listing splits its fields across TWO <dl>
# elements. Reading only the first one (what lazyflat did) silently loses WBS.
PAGE = """
<div id="apartment-21792" class="item">
  <a href="https://www.gewobag.de/angebot/1">Alle Details</a>
  <dl>
    <dt>Adresse:</dt><dd>Kandeler Weg 1, 13583, Spandau</dd>
    <dt>Zimmeranzahl:</dt><dd>2,0</dd>
    <dt>Wohnfläche:</dt><dd>60,00 m²</dd>
    <dt>Kaltmiete:</dt><dd>700,00 €</dd>
    <dt>Nebenkosten:</dt><dd>167,80 €</dd>
    <dt>Gesamtmiete:</dt><dd>867,80 €</dd>
  </dl>
  <dl>
    <dt>WBS:</dt><dd>erforderlich</dd>
    <dt>Etage:</dt><dd>11 von (insg. 12)</dd>
    <dt>Baujahr:</dt><dd>1974</dd>
  </dl>
</div>
<div id="apartment-21791">
  <a href="/relativer/pfad">alle details</a>
  <dl><dt>Adresse</dt><dd>Musterweg 2, 10115, Mitte</dd></dl>
  <dl><dt>WBS</dt><dd>nicht erforderlich</dd></dl>
</div>
<div id="apartment-21790">
  <dl><dt>Adresse</dt><dd>Ohne Link 3, 12043, Neukölln</dd></dl>
</div>
"""


def test_parses_every_listing():
    assert len(Scraper()._parse(PAGE)) == 3


def test_reads_fields_from_the_second_dl_too():
    """Regression: only reading the first <dl> loses WBS, which the whole
    WBS filter depends on."""
    first = Scraper()._parse(PAGE)[0]
    assert first["WBS"] == "erforderlich"
    assert first["Etage"] == "11 von (insg. 12)"
    assert first["Baujahr"] == "1974"


def test_source_id_and_absolute_link():
    first = Scraper()._parse(PAGE)[0]
    assert first["id"] == "21792"
    assert first["link"] == "https://www.gewobag.de/angebot/1"


def test_relative_links_are_made_absolute():
    second = Scraper()._parse(PAGE)[1]
    assert second["link"] == "https://www.inberlinwohnen.de/relativer/pfad"


def test_listing_without_a_detail_link_falls_back_to_the_portal():
    third = Scraper()._parse(PAGE)[2]
    assert third["link"] == Scraper.BASE_URL


def test_parsed_listing_feeds_the_flat_model():
    flat = Flat(Scraper()._parse(PAGE)[0])
    assert flat.rooms == 2.0
    assert flat.total_rent == 867.80
    assert flat.wbs == "erforderlich"
    assert flat.district == "Spandau"
    assert flat.provider == "gewobag.de"


def test_empty_page_yields_no_listings():
    assert Scraper()._parse("<html><body>nichts</body></html>") == []
