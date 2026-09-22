"""One scraped listing.

The scraper hands over whatever German <dt>/<dd> labels inberlinwohnen.de
ships; this maps the ones we care about onto attributes and keeps the rest
in raw_data.
"""
import json
import re

from urllib.parse import quote

from app.berlin_districts import district_for_address
from app.providers import provider_for_link


class Flat:
    def __init__(self, data: dict):
        self.link = data.get("link", "")
        self.source_id = str(data.get("id", ""))
        self.address = data.get("Adresse", "")
        self.rooms = self._parse_german_float(data.get("Zimmeranzahl", "0"))
        self.size = self._parse_german_float(data.get("Wohnfläche", "0"))
        self.cold_rent = self._parse_german_float(data.get("Kaltmiete", "0"))
        self.utilities = self._parse_german_float(data.get("Nebenkosten", "0"))
        self.total_rent = self._parse_german_float(data.get("Gesamtmiete", "0"))
        self.available_from = data.get("Bezugsfertig ab", "")
        self.published_on = data.get("Eingestellt am", "")
        self.wbs = data.get("WBS", "")
        self.floor = data.get("Etage", "")
        self.bathrooms = data.get("Badezimmer", "")
        self.year_built = data.get("Baujahr", "")
        self.heating = data.get("Heizung", "")
        self.energy_carrier = data.get("Hauptenergieträger", "")
        self.energy_value = data.get("Energieverbrauchskennwert", "")
        self.energy_certificate = data.get("Energieausweis", "")
        self.raw_data = data
        # Identity is the listing URL, same rule lazyflat used.
        self.id = self.link
        self.address_link_gmaps = (
            f"https://www.google.com/maps/search/?api=1&query={quote(self.address)}"
        )

    @staticmethod
    def _parse_german_float(text) -> float:
        """"1.234,56 €" -> 1234.56. Anything unparseable -> 0.0."""
        if not text:
            return 0.0
        clean_text = re.sub(r"[^\d,.]", "", str(text))
        clean_text = clean_text.replace(".", "").replace(",", ".")
        try:
            return float(clean_text)
        except ValueError:
            return 0.0

    @property
    def sqm_price(self) -> float:
        if self.size > 0:
            return self.total_rent / self.size
        return 0.0

    @property
    def district(self) -> str | None:
        return district_for_address(self.address)

    @property
    def provider(self) -> str:
        return provider_for_link(self.link)

    def to_payload(self) -> dict:
        """The row shape db.upsert_flat expects, with district and provider
        already derived so matching never has to re-derive them."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "link": self.link,
            "provider": self.provider,
            "address": self.address,
            "district": self.district,
            "rooms": self.rooms,
            "size": self.size,
            "total_rent": self.total_rent,
            "sqm_price": self.sqm_price,
            "wbs": self.wbs,
            "address_link_gmaps": self.address_link_gmaps,
            "payload_json": json.dumps(
                {
                    "cold_rent": self.cold_rent,
                    "utilities": self.utilities,
                    "available_from": self.available_from,
                    "published_on": self.published_on,
                    "floor": self.floor,
                    "bathrooms": self.bathrooms,
                    "year_built": self.year_built,
                    "heating": self.heating,
                    "energy_carrier": self.energy_carrier,
                    "energy_value": self.energy_value,
                    "energy_certificate": self.energy_certificate,
                    "raw_data": self.raw_data,
                },
                ensure_ascii=False,
                default=str,
            ),
        }

    def __repr__(self) -> str:
        return f"<Flat {self.address!r} {self.rooms}Zi {self.total_rent}€>"
