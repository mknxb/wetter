"""Holt die Pegelwerte des Hochwassernachrichtendienstes Bayern (HND) fuer das
Einzugsgebiet von Regen und Chamb und schreibt sie nach pegel.json.
Die Werte stehen als data-Attribute an den Pegelsymbolen der HND-Uebersichtsseite."""
import json, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

URL = "https://www.hnd.bayern.de/pegel"
PREFIX = "152"            # Pegelnummern im Einzugsgebiet des Regen (inkl. Chamb)
EXTRA = {"10081004", "10078000", "10088003"}   # Donau: Deggendorf, Pfelling, Hofkirchen
OUT = "pegel.json"
KEEP_H = 48               # Verlauf, der fuer die Tendenz aufgehoben wird
TZ = ZoneInfo("Europe/Berlin")


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            self.href = a.get("href")
        elif tag == "img" and re.fullmatch(r"p\d{8}", a.get("id") or ""):
            pid = a["id"][1:]
            if pid.startswith(PREFIX) or pid in EXTRA:
                self.rows.append({**a, "_id": pid, "_href": self.href})

    def handle_endtag(self, tag):
        if tag == "a":
            self.href = None


def num(v):
    v = (v or "").strip().replace(".", "").replace(",", ".") if v and v.count(",") else (v or "").strip()
    try:
        return float(v)
    except ValueError:
        return None


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "wetter-bayerwald (privat, GitHub Pages)"})
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    p = P()
    p.feed(html)
    if not p.rows:
        sys.exit("Keine Pegel gefunden - Aufbau der HND-Seite geaendert?")

    old = {}
    if os.path.exists(OUT):
        try:
            old = {s["id"]: s for s in json.load(open(OUT, encoding="utf-8")).get("stations", [])}
        except Exception:
            old = {}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=KEEP_H)
    stations = []
    for r in p.rows:
        t = None
        if r.get("data-datum"):
            try:
                t = datetime.strptime(r["data-datum"], "%d.%m.%Y, %H:%M").replace(tzinfo=TZ).astimezone(timezone.utc)
            except ValueError:
                pass
        level = num(r.get("data-wert"))
        hist = [h for h in old.get(r["_id"], {}).get("hist", []) if datetime.fromisoformat(h[0]) >= cutoff]
        if t and level is not None and (not hist or hist[-1][0] != t.isoformat()):
            hist.append([t.isoformat(), level])
        href = r.get("_href") or ""
        stations.append({
            "id": r["_id"],
            "name": (r.get("data-name") or "").strip(),
            "river": (r.get("data-zeile2") or "").strip(),
            "level": level,
            "flow": num(r.get("data-wert2")),
            "stage": int(r["data-ms"]) if (r.get("data-ms") or "").strip().isdigit() else None,
            "time": t.isoformat() if t else None,
            "hint": (r.get("data-stoerung") or "").strip() or None,
            "url": href if href.startswith("http") else ("https://www.hnd.bayern.de" + href if href else None),
            "hist": hist,
        })
    stations.sort(key=lambda s: s["id"])
    json.dump({"updated": now.isoformat(), "source": URL, "stations": stations},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(stations)} Pegel geschrieben")


if __name__ == "__main__":
    main()
