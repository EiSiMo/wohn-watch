# wohn-watch

Ein Telegram-Bot, der den Wohnungsfinder von **inberlinwohnen.de** beobachtet und
neue passende Inserate sofort in den Chat schickt.

Kein Konto, keine Web-Oberfläche, keine Anmeldung: man schreibt den Bot an, klickt
sich durch ein kurzes Setup und bekommt ab da Benachrichtigungen.

```
Telegram ──polling──► wohn-watch ──scrape──► inberlinwohnen.de
                          │
                          └── SQLite (Chats, Filter, Inserate, Zustellprotokoll)
```

Ein Prozess, ein Container. Die Scrape-Schleife läuft als `JobQueue`-Job im
Event-Loop des Bots; der synchrone Scraper wird per `asyncio.to_thread`
ausgeführt.

## Funktionsweise

Alle 60 Sekunden wird der öffentliche Wohnungsfinder geladen — **ohne Konto**.
Die Seite `/wohnungsfinder` liefert dieselben Inserate und dieselben Felder wie
der eingeloggte Bereich, WBS eingeschlossen. Gelesen wird nur die erste Seite:
sie enthält die 10 neuesten Inserate (`created_at desc`), und es erscheinen nie
mehr als eine Handvoll auf einmal.

Jedes Inserat landet in der
`flats`-Tabelle — der Primärschlüssel ist die Inserats-URL, und `INSERT OR IGNORE`
meldet zurück, ob es neu war. Nur wirklich neue Inserate werden gegen die Filter
aller aktiven Chats geprüft und verschickt.

**Kein Rückblick.** Beim ersten Lauf gegen eine leere Datenbank werden alle
Inserate eingelesen, aber nichts verschickt (`meta.bootstrap_done`). Und jeder
Chat bekommt beim Aktivieren einen Zeitstempel (`chats.notify_since`) — es werden
ausschließlich Inserate gemeldet, die danach gefunden wurden. Ein neuer Nutzer
wird so nie von zweihundert alten Anzeigen begraben.

## Filter

| Kriterium | Eingabe |
|---|---|
| Zimmer min/max | Presets oder Freitext (`2,5` funktioniert) |
| max. Gesamtmiete | Presets oder Freitext |
| min. Wohnfläche | Presets oder Freitext |
| WBS | egal / nur ohne / nur mit |
| Bezirke | 12 Berliner Bezirke, Mehrfachauswahl |
| Anbieter | Gewobag, degewo, GESOBAU, HOWOGE, Stadt und Land, WBM |

Bezirk und Anbieter gelten als „kein Filter", solange nichts abgewählt ist.
Der Bezirk wird aus der PLZ in der Adresse abgeleitet, der Anbieter aus der
Domain der Inserats-URL.

## Befehle

`/start` `/filter` `/status` `/pause` `/resume` `/stop` `/hilfe`

`/stop` löscht Chat, Filter und Zustellprotokoll per `ON DELETE CASCADE`
endgültig.

## Lokal starten

```bash
cp .env.example .env     # nur TELEGRAM_BOT_TOKEN eintragen
docker compose up -d --build
docker compose logs -f
```

Ohne Docker:

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
DATA_DIR=./data .venv/bin/python -m app.main
```

## Tests

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest
```

Die Tests laufen ohne Netzwerk und ohne Telegram-Token.

## Scraper prüfen

Ein einzelner Live-Durchlauf, der zeigt welche Felder die Seite gerade liefert und
auf welche Domains die Inserate zeigen — nützlich, wenn der Anbieter-Filter
auffällig wenig trifft (braucht keine Zugangsdaten):

```bash
.venv/bin/python -m app.scraper
```

## Deployment (Coolify)

Als *Docker Compose*-Resource anlegen, die Variablen aus `.env.example` in die
Env-UI eintragen, fertig. Es wird **keine Domain** gebraucht — der Bot pollt
ausgehend und lauscht auf keinem Port.

Der Healthcheck fragt die Datenbank, wann der letzte Scrape erfolgreich war;
kein HTTP-Server nötig.

> `${SOURCE_COMMIT}` nicht in der `docker-compose.yml` referenzieren — Coolify
> behandelt das sonst als Nutzervariable und injiziert den echten Commit-SHA
> nicht mehr.

## Herkunft

Scraper, Matching-Logik, PLZ→Bezirk-Tabelle und das Format der
Match-Nachricht stammen aus [lazyflat](https://git.moritz.run/moritz/lazyflat);
Web-UI und der experimentelle Auto-Bewerber sind dabei weggefallen.

Zwei Dinge macht wohn-watch anders als lazyflat: es liest die öffentliche Seite
statt sich einzuloggen, und es wertet **alle** `<dl>`-Blöcke einer Anzeige aus.
lazyflat las nur den ersten und verlor damit öffentlich das WBS-Feld.
