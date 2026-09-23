<p align="center">
  <img src="assets/logo.png" width="160" alt="wohn-watch Logo">
</p>

<h1 align="center">wohn-watch</h1>

<p align="center">
  Telegram-Bot, der dir neue Wohnungen der landeseigenen Berliner Wohnungsgesellschaften sofort aufs Handy schickt.
</p>

<p align="center">
  <img src="assets/screenshot-1.png" width="30%" alt="Neue Inserate im Chat">
  &nbsp;
  <img src="assets/screenshot-2.png" width="30%" alt="Filter einstellen">
  &nbsp;
  <img src="assets/screenshot-3.png" width="30%" alt="Begrüßung mit /start">
</p>

Günstige Wohnungen sind in Berlin oft nach wenigen Minuten weg. wohn-watch schaut
rund um die Uhr auf [inberlinwohnen.de](https://inberlinwohnen.de) nach und schickt
dir jedes neue Angebot, das zu deiner Suche passt, direkt per Telegram. Dabei sind
HOWOGE, degewo, Gewobag, GESOBAU, Stadt und Land, WBM und berlinovo.

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#befehle">Befehle</a> ·
  <a href="#filter">Filter</a> ·
  <a href="#lizenz">Lizenz</a>
</p>

## Install

Du brauchst Docker und einen Bot-Token von [@BotFather](https://t.me/BotFather).

```bash
git clone https://github.com/EiSiMo/wohn-watch.git && cd wohn-watch
cp .env.example .env        # TELEGRAM_BOT_TOKEN eintragen, alles andere ist optional
docker compose up -d --build
```

Du brauchst keine Domain und keinen offenen Port, weil der Bot Telegram von sich
aus abfragt. Die SQLite-Datenbank liegt im Volume `wohnwatch_data`.

## Befehle

| Befehl | Funktion |
|---|---|
| `/start` | Einführung und Einrichtung |
| [`/filter`](#filter) | Suche ändern |
| `/status` | Filter und Statistik |
| `/pause` | Benachrichtigungen aussetzen |
| `/resume` | Benachrichtigungen fortsetzen |
| `/sprache` | Sprache wechseln (Deutsch/Englisch) |
| `/problem` | Problem melden |
| `/stop` | Alle Daten löschen |
| `/hilfe` | Übersicht aller Befehle |

### Filter

| Filter | Erklärung |
|---|---|
| Zimmer | Mindest- und Höchstzahl, halbe Zimmer möglich |
| Miete | Höchste Gesamtmiete in € |
| Fläche | Mindestgröße in m² |
| WBS | egal, nur ohne oder nur mit WBS |
| Bezirke | Eine beliebige Auswahl der 12 Berliner Bezirke |
| Anbieter | Eine beliebige Auswahl der Wohnungsgesellschaften |

## Lizenz

[MIT](LICENSE)
