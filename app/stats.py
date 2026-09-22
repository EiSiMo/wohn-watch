"""`python -m app.stats` — what the bot has been doing.

Read-only report over the usage log: lifetime totals that survive deletions,
per-day traffic, command popularity and the most recently active chats.
"""
import argparse
import collections

from app import db


def _bar(n: int, scale: int, width: int = 28) -> str:
    return "█" * max(1, round(n / scale * width)) if n else ""


def _fmt_ts(ts: str | None) -> str:
    return (ts or "")[:16].replace("T", " ") or "—"


def report(days: int, chats: int, tail: int) -> None:
    counters = db.counters()

    print("\n=== Gesamt (überlebt /stop) ===")
    created = counters.get("chats_created_total", 0)
    deleted = counters.get("chats_deleted_total", 0)
    print(f"  Chats angelegt      {created}")
    print(f"  Chats gelöscht      {deleted}")
    print(f"  davon noch aktiv    {db.count_chats()}")
    for key, label in (
        ("ev_in_command", "Befehle empfangen"),
        ("ev_in_text", "Texte empfangen"),
        ("ev_in_callback", "Button-Klicks"),
        ("ev_in_media", "Medien empfangen"),
        ("ev_out_match", "Treffer verschickt"),
        ("ev_out_reply", "Antworten verschickt"),
    ):
        print(f"  {label:22}{counters.get(key, 0)}")

    print(f"\n=== Verkehr der letzten {days} Tage ===")
    per_day = db.events_per_day(days)
    if not per_day:
        print("  (noch nichts)")
    else:
        totals: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for row in per_day:
            totals[row["day"]][f'{row["direction"]}/{row["kind"]}'] += row["n"]
        scale = max(sum(c.values()) for c in totals.values())
        for day in sorted(totals, reverse=True):
            c = totals[day]
            n = sum(c.values())
            detail = " ".join(f"{k}={v}" for k, v in c.most_common())
            print(f"  {day}  {n:4d} {_bar(n, scale)}")
            print(f"              {detail}")

    print("\n=== Befehle ===")
    rows = db.command_counts()
    if not rows:
        print("  (noch nichts)")
    for row in rows:
        print(f"  {row['command']:12} {row['n']}")

    print(f"\n=== Aktivste Chats (max {chats}) ===")
    rows = db.chat_activity(chats)
    if not rows:
        print("  (noch nichts)")
    else:
        print(f"  {'chat_id':>12}  {'status':8} {'nachr.':>7} {'treffer':>8}  zuletzt")
        for row in rows:
            print(f"  {row['chat_id']:>12}  {row['state']:8} {row['msgs']:>7} "
                  f"{row['matches']:>8}  {_fmt_ts(row['last_seen'])}")

    if tail:
        print(f"\n=== Letzte {tail} Ereignisse ===")
        for e in db.recent_events(tail):
            print(f"  {_fmt_ts(e['ts'])}  {e['chat_id'] or '-':>12}  "
                  f"{e['direction']:3} {e['kind']:9} {e['detail'][:60]}")

    print(f"\nInserate in der DB: {db.count_flats()}   "
          f"letzter Scrape: {_fmt_ts(db.get_meta('last_scrape_at')) or '—'}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="wohn-watch Nutzungsstatistik")
    ap.add_argument("--days", type=int, default=14, help="Tage im Verkehrsverlauf")
    ap.add_argument("--chats", type=int, default=20, help="Chats in der Aktivitätsliste")
    ap.add_argument("--tail", type=int, default=20, help="letzte Ereignisse (0 = aus)")
    args = ap.parse_args()
    # Idempotent, and it means the report also works before the bot's first run.
    db.init_db()
    report(args.days, args.chats, args.tail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
