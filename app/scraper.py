"""inberlinwohnen.de scraper.

Unchanged in substance from lazyflat's alert/scraper.py — same Laravel CSRF
login, same headers, same `apartment-<n>` / <dl> parsing. What changed: one
session is kept across scrapes and we only re-login when the site actually
logged us out, instead of building a fresh session every 60 seconds.
"""
import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("wohnwatch.scraper")

_CSRF_RE = re.compile(r'name="csrf-token" content="([^"]+)"')
_APARTMENT_RE = re.compile(r"^apartment-\d+")


class Scraper:
    URL_LOGIN = "https://www.inberlinwohnen.de/login"
    URL_FINDER = "https://www.inberlinwohnen.de/mein-bereich/wohnungsfinder"
    BASE_URL = "https://www.inberlinwohnen.de"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "de,en;q=0.9,en-US;q=0.8",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session: requests.Session | None = None

    # -- session ------------------------------------------------------------

    def _new_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update(self.HEADERS)
        return s

    def _login(self) -> bool:
        """Fresh session + Laravel form login. Returns True on success."""
        if not self.username or not self.password:
            logger.critical("BERLIN_WOHNEN credentials missing — nothing to log in with")
            return False

        session = self._new_session()
        logger.info("fetching inberlinwohnen.de login page")
        resp_login_page = session.get(self.URL_LOGIN, timeout=30)
        token_search = _CSRF_RE.search(resp_login_page.text)
        if not token_search:
            logger.critical("no CSRF token found on login page")
            return False

        payload = {
            "_token": token_search.group(1),
            "email": self.username,
            "password": self.password,
            "remember": "on",
        }
        headers = dict(self.HEADERS, Referer=self.URL_LOGIN)

        logger.info("attempting login")
        resp = session.post(self.URL_LOGIN, data=payload, headers=headers, timeout=30)

        if not resp.ok or "login" in resp.url:
            logger.critical("login failed (status=%s url=%s)", resp.status_code, resp.url)
            return False

        logger.info("login successful")
        self.session = session
        return True

    @staticmethod
    def _looks_logged_out(resp: requests.Response) -> bool:
        # 419 is Laravel's "session/CSRF expired".
        return resp.status_code in (401, 403, 419) or "login" in resp.url.lower()

    # -- scraping -----------------------------------------------------------

    def fetch(self) -> list[dict] | None:
        """Return the current listings, or None on a transient failure.

        None means "try again later with backoff" — the caller must never
        treat it as "there are no flats".
        """
        try:
            if self.session is None and not self._login():
                return None

            resp = self._get_finder()
            if resp is not None and self._looks_logged_out(resp):
                logger.info("session expired — logging in again")
                self.session = None
                if not self._login():
                    return None
                resp = self._get_finder()

            if resp is None:
                return None
            if not resp.ok:
                logger.warning("finder page returned HTTP %s", resp.status_code)
                self.session = None
                return None

            return self._parse(resp.text)
        except requests.RequestException as e:
            logger.warning("scrape failed: %s", e)
            self.session = None
            return None

    def _get_finder(self) -> requests.Response | None:
        assert self.session is not None
        logger.debug("fetching flat list")
        self.session.headers.update({"Referer": f"{self.BASE_URL}/mein-bereich"})
        return self.session.get(self.URL_FINDER, timeout=30)

    def _parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        apartment_divs = soup.find_all("div", id=_APARTMENT_RE)
        logger.info("found %d apartments on page", len(apartment_divs))

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

            details_list = div.find("dl")
            if details_list:
                for dt in details_list.find_all("dt"):
                    key = dt.get_text(strip=True).rstrip(":")
                    dd = dt.find_next_sibling("dd")
                    if dd:
                        data[key] = dd.get_text(strip=True)

            flats_data.append(data)

        return flats_data


def _dump() -> int:
    """`python -m app.scraper` — one live scrape, for verifying the parser and
    the provider-domain coverage before trusting the Anbieter filter."""
    import collections
    from urllib.parse import urlparse

    from app import settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    scraper = Scraper(settings.BERLIN_WOHNEN_USERNAME, settings.BERLIN_WOHNEN_PASSWORD)
    flats = scraper.fetch()
    if flats is None:
        print("scrape failed")
        return 1

    print(f"\n{len(flats)} Wohnungen\n")
    keys = collections.Counter(k for f in flats for k in f)
    print("<dl> keys:")
    for k, n in keys.most_common():
        print(f"  {n:4d}  {k}")
    print("\nLink-Domains:")
    for host, n in collections.Counter(
        urlparse(f["link"]).netloc.lower().removeprefix("www.") for f in flats
    ).most_common():
        print(f"  {n:4d}  {host}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_dump())
