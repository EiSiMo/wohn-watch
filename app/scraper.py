"""inberlinwohnen.de scraper.

Reads the public Wohnungsfinder. Two things differ from lazyflat's
alert/scraper.py, both verified against the live site:

* **No login.** lazyflat authenticated and scraped /mein-bereich/wohnungsfinder.
  The public /wohnungsfinder serves the same 364 listings, and once every <dl>
  is read (see below) the same fields — including WBS. That removes the shared
  account, the Laravel CSRF dance, session expiry and re-login entirely.
* **Every <dl>, not just the first.** lazyflat read `div.find('dl')`. Publicly
  each listing splits its data across two <dl> elements, so the first one alone
  loses WBS, Etage, Baujahr, Heizung and the energy fields.

Only the first page is read. It holds the 10 newest listings (the finder sorts
`created_at desc`), which is ample: listings arrive a handful at a time.
"""
import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("wohnwatch.scraper")

_APARTMENT_RE = re.compile(r"^apartment-\d+")


class Scraper:
    URL_FINDER = "https://www.inberlinwohnen.de/wohnungsfinder"
    BASE_URL = "https://www.inberlinwohnen.de"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "de,en;q=0.9,en-US;q=0.8",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def fetch(self) -> list[dict] | None:
        """The newest listings, or None on a transient failure.

        None means "back off and retry" — the caller must never read it as
        "there are no flats".
        """
        try:
            resp = self.session.get(self.URL_FINDER, timeout=30)
        except requests.RequestException as e:
            logger.warning("scrape failed: %s", e)
            return None

        if not resp.ok:
            logger.warning("finder returned HTTP %s", resp.status_code)
            return None

        return self._parse(resp.text)

    def _parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        apartment_divs = soup.find_all("div", id=_APARTMENT_RE)
        logger.debug("found %d apartments on page", len(apartment_divs))

        flats_data = []
        for div in apartment_divs:
            data = {"id": div["id"].replace("apartment-", "")}

            href = None
            for link in div.find_all("a"):
                if "alle details" in link.get_text(strip=True).lower():
                    href = link.get("href")
                    break
            if href:
                data["link"] = href if href.startswith("http") else self.BASE_URL + href
            else:
                data["link"] = self.BASE_URL

            # Every <dl>: the listing's fields are split across two of them.
            for dl in div.find_all("dl"):
                for dt in dl.find_all("dt"):
                    dd = dt.find_next_sibling("dd")
                    if dd:
                        data[dt.get_text(strip=True).rstrip(":")] = dd.get_text(strip=True)

            flats_data.append(data)

        return flats_data


def _dump() -> int:
    """`python -m app.scraper` — one live scrape, for checking the parser and
    the provider-domain coverage."""
    import collections
    from urllib.parse import urlparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    flats = Scraper().fetch()
    if flats is None:
        print("scrape failed")
        return 1

    print(f"\n{len(flats)} Wohnungen\n")
    print("Felder:")
    for k, n in collections.Counter(k for f in flats for k in f).most_common():
        print(f"  {n:4d}  {k}")
    print("\nLink-Domains:")
    for host, n in collections.Counter(
        urlparse(f["link"]).netloc.lower().removeprefix("www.") for f in flats
    ).most_common():
        print(f"  {n:4d}  {host}")
    print("\nEingestellt am:")
    for day, n in collections.Counter(f.get("Eingestellt am") for f in flats).most_common():
        print(f"  {n:4d}  {day}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_dump())
