"""Every user-facing German string, in one place."""

INTRO = (
    "*Wohn-Watch* 🏠\n\n"
    "Ich beobachte rund um die Uhr den Wohnungsfinder von *inberlinwohnen.de* — "
    "das gemeinsame Portal der sechs landeseigenen Berliner Wohnungsbaugesellschaften "
    "(Gewobag, degewo, GESOBAU, HOWOGE, Stadt und Land, WBM).\n\n"
    "Du stellst hier einmal kurz ein, was du suchst. Sobald ein neues Inserat dazu passt, "
    "schicke ich es dir sofort in diesen Chat — mit Adresse, Miete, Fläche und Link zur Anzeige.\n\n"
    "Kein Konto, keine Anmeldung, kostenlos. Mit /stop löschst du jederzeit alle deine Daten.\n\n"
    "Lass uns deinen Filter einrichten 👇"
)

INTRO_RETURNING = (
    "Willkommen zurück 🏠\n\n"
    "Dein Filter: _{summary}_\n"
    "Status: *{state}*\n\n"
    "Mit /filter änderst du deine Suche, /status zeigt Details."
)

HELP = (
    "*Wohn-Watch — Hilfe*\n\n"
    "Ich melde dir neue Wohnungen von inberlinwohnen.de, die zu deinem Filter passen.\n\n"
    "*Befehle*\n"
    "/start – Einführung und Einrichtung\n"
    "/filter – Suche ändern\n"
    "/status – aktueller Filter und Statistik\n"
    "/pause – Benachrichtigungen aussetzen\n"
    "/resume – Benachrichtigungen fortsetzen\n"
    "/problem – Problem melden oder Wunsch loswerden\n"
    "/stop – alle Daten löschen\n"
    "/hilfe – diese Übersicht\n\n"
    "*Deine Daten*\n"
    "Gespeichert werden deine Chat-ID, dein Filter und ein Protokoll deiner "
    "Nachrichten an mich — damit ich sehe, ob der Bot funktioniert und genutzt wird. "
    "Keine Namen, keine Telefonnummer, keine Weitergabe an Dritte. "
    "/stop löscht alles davon sofort und vollständig.\n\n"
    "*Wichtig*\n"
    "Ich bewerbe dich nicht automatisch. Du bekommst den Link, bewerben musst du dich selbst — "
    "bei den begehrten Wohnungen zählt jede Minute.\n\n"
    "Quellcode: https://git.moritz.run/moritz/wohn-watch"
)

SETUP_DONE = (
    "✅ *Alarme sind aktiv.*\n\n"
    "Dein Filter: _{summary}_\n\n"
    "Ab jetzt melde ich dir jede neue passende Wohnung. Wohnungen, die schon vor "
    "dieser Einrichtung online waren, bekommst du bewusst nicht — sonst stünden hier "
    "gleich hundert veraltete Inserate.\n\n"
    "⚡️ *Sei schnell.* Die Inserate sind oft nach rund 30 Minuten wieder offline. "
    "Wenn eine Nachricht kommt, lohnt es sich, direkt zu reagieren und dich gleich "
    "zu bewerben — nicht erst abends.\n\n"
    "Mit /pause machst du kurz Ruhe, mit /filter änderst du die Suche."
)

MENU_TITLE = "*Dein Filter*\n_{summary}_"

STATUS = (
    "*Status*\n\n"
    "Benachrichtigungen: *{state}*\n"
    "Filter: _{summary}_\n"
    "Bisher gemeldet: *{sent}* Wohnungen\n"
    "Beobachtete Inserate: *{flats}*\n"
    "Letzte Prüfung: {last_scrape}"
)

STATE_ACTIVE = "aktiv"
STATE_PAUSED = "pausiert"
STATE_NEW = "noch nicht eingerichtet"

NOT_SET_UP = "Du hast noch keinen Filter. Starte mit /start."

PAUSED = "⏸ Benachrichtigungen pausiert. Mit /resume geht's weiter."
ALREADY_PAUSED = "Ist schon pausiert. Mit /resume geht's weiter."
RESUMED = (
    "▶️ Benachrichtigungen laufen wieder.\n\n"
    "Ich starte ab jetzt — was während der Pause online ging, hole ich nicht nach."
)
ALREADY_ACTIVE = "Läuft bereits. /pause setzt aus."

DELETE_CONFIRM = (
    "Wirklich alles löschen?\n\n"
    "Dein Filter und alle gespeicherten Daten zu diesem Chat verschwinden endgültig. "
    "Du kannst jederzeit mit /start neu anfangen."
)
DELETED = "🗑 Alles gelöscht. Danke fürs Ausprobieren — mit /start bist du jederzeit wieder dabei."
DELETE_ABORTED = "Abgebrochen, es bleibt alles wie es ist."

ASK_NUMBER = {
    "rooms_min": "Wie viele Zimmer *mindestens*? Schick mir eine Zahl, z. B. `2` oder `2,5`.",
    "rooms_max": "Wie viele Zimmer *höchstens*? Schick mir eine Zahl, z. B. `3,5`.",
    "max_rent": "Wie hoch darf die *Gesamtmiete* höchstens sein? Zahl in Euro, z. B. `1250`.",
    "min_size": "Wie viel *Wohnfläche* mindestens? Zahl in m², z. B. `60`.",
}

ASK_HINT = "\n\n_Abbrechen mit /filter._"

BAD_NUMBER = "Das konnte ich nicht als Zahl lesen. Versuch's nochmal, z. B. `1250`."
OUT_OF_RANGE = "Der Wert wirkt unrealistisch ({lo}–{hi}). Schick mir bitte eine andere Zahl."

UNEXPECTED_TEXT = (
    "Damit kann ich nichts anfangen 🤔 Ich verstehe nur Befehle:\n\n"
    "/start – Einführung und Einrichtung\n"
    "/filter – Suche ändern\n"
    "/status – aktueller Filter und Statistik\n"
    "/pause – Benachrichtigungen aussetzen\n"
    "/resume – Benachrichtigungen fortsetzen\n"
    "/problem – etwas stimmt nicht?\n"
    "/stop – alle Daten löschen\n"
    "/hilfe – ausführliche Übersicht"
)

SUPPORT_EMAIL = "wohnwatch@moritz.run"

PROBLEM = (
    "*Etwas stimmt nicht?*\n\n"
    "Schreib mir einfach eine Mail — Fehler, komische Treffer, fehlende "
    "Wohnungen oder Wünsche, alles willkommen:\n\n"
    f"{SUPPORT_EMAIL}\n\n"
    "Hilfreich für mich: was du erwartet hast und was stattdessen passiert ist. "
    "Mit /status siehst du deinen aktuellen Filter — den gerne mitschicken."
)

STALE_MENU = "Dieses Menü ist veraltet — ich habe dir ein frisches geöffnet."

OVERFLOW = (
    "… und *{n}* weitere passende Wohnungen in dieser Runde.\n"
    "Dein Filter ist ziemlich weit gefasst — mit /filter kannst du ihn enger stellen."
)

WIZARD_STEP = "*Schritt {n} von {total}*\n\n{question}"

Q_ROOMS_MIN = "Wie viele Zimmer sollen es *mindestens* sein?"
Q_ROOMS_MAX = "Und *höchstens*?"
Q_RENT = "Was darf die *Gesamtmiete* höchstens kosten?"
Q_SIZE = "Wie viel *Wohnfläche* brauchst du mindestens?"
Q_WBS = (
    "Brauchst du Wohnungen *mit* oder *ohne* WBS?\n\n"
    "_Ein Wohnberechtigungsschein (WBS) ist bei vielen günstigen Wohnungen Pflicht. "
    "Hast du keinen, wähle „nur ohne WBS\"._"
)
Q_DISTRICTS = (
    "In welchen *Bezirken* suchst du?\n\n"
    "_Nichts auswählen = alle Bezirke._"
)
Q_PROVIDERS = (
    "Von welchen *Anbietern*?\n\n"
    "_Nichts auswählen = alle Anbieter._"
)

SUMMARY_CONFIRM = (
    "Das habe ich mir gemerkt:\n\n_{summary}_\n\n"
    "Passt das so?"
)

FILTER_CLEARED = "Filter zurückgesetzt — du bekommst jetzt wieder alle neuen Wohnungen."
