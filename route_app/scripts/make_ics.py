#!/usr/bin/env python3
"""make_ics.py — генерация ICS-календаря похода для импорта в Google Календарь.

Использование:
  python3 make_ics.py events.json out.ics

events.json:
[
  {
    "summary": "День 3 · Артуч → Куликалон (2850 м)",
    "start": "2026-09-08T08:00:00",       # локальное время пояса tzid
    "end":   "2026-09-08T17:00:00",       # или "date": "2026-09-08" для события на весь день
    "tzid": "Asia/Dushanbe",              # Europe/Minsk, Asia/Tashkent, Asia/Dushanbe...
    "location": "Альплагерь Артуч",
    "description": "~7 км, +700 м. Азимут 123° ЮВ.",
    "alarms_min": [720, 60]               # за сколько минут напомнить (можно [])
  }
]

Правила: запятые и точки с запятой в текстах экранируются (\\, \\;); строки ≤75 октетов
не гарантируются Google-импортом, но folding не обязателен; VTIMEZONE Google подставит
сам по TZID — главное, чтобы TZID был из базы IANA.
"""
import argparse, json, sys
from datetime import datetime


def esc(text):
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def make_event(ev):
    lines = ["BEGIN:VEVENT", f"UID:{abs(hash(json.dumps(ev, sort_keys=True)))}@routegen",
             f"DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}"]
    tzid = ev.get("tzid", "Europe/Minsk")
    if ev.get("date"):  # событие на весь день
        d = ev["date"].replace("-", "")
        lines += [f"DTSTART;VALUE=DATE:{d}", f"DTEND;VALUE=DATE:{d}"]
    else:
        lines += [f"DTSTART;TZID={tzid}:{ev['start'].replace('-', '').replace(':', '')}",
                  f"DTEND;TZID={tzid}:{ev['end'].replace('-', '').replace(':', '')}"]
    lines.append(f"SUMMARY:{esc(ev['summary'])}")
    if ev.get("location"):
        lines.append(f"LOCATION:{esc(ev['location'])}")
    if ev.get("description"):
        lines.append(f"DESCRIPTION:{esc(ev['description'])}")
    for mins in ev.get("alarms_min", []):
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY",
                  f"DESCRIPTION:{esc(ev['summary'])}",
                  f"TRIGGER:-PT{mins}M", "END:VALARM"]
    lines.append("END:VEVENT")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("events")
    ap.add_argument("out")
    args = ap.parse_args()

    events = json.load(open(args.events, encoding="utf-8"))
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//routegen//RU",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for ev in events:
        lines += make_event(ev)
    lines.append("END:VCALENDAR")
    open(args.out, "w", encoding="utf-8", newline="\r\n").write("\r\n".join(lines) + "\r\n")
    print(f"✓ {args.out}: {len(events)} событий", file=sys.stderr)


if __name__ == "__main__":
    main()
