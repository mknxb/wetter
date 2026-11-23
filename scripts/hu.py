"""Holt Daten fuer die Region Ungarn der Wetterseite und schreibt sie nach hu.json:
- 10-Minuten-Messwerte aller Automatikstationen von HungaroMet (odp.met.hu, offene Daten),
  dazu Tiefst-/Hoechstwerte 12 h und 24 h, Regen heute und letzte Stunde, Gamma-Ortsdosisleistung
- Unwetterwarnungen fuer Ungarn ueber MeteoAlarm (Atom-Feed)
Jede Quelle ist unabhaengig: faellt eine aus, bleibt der Rest erhalten (Fehler unter "errors").
Quelle der Messwerte: HungaroMet Nonprofit Zrt. (Nennung ist Nutzungsbedingung)."""
import csv, io, json, re, sys, urllib.error, urllib.request, zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

OUT = "hu.json"
UA = {"User-Agent": "wetter-bayerwald (privat, GitHub Pages)"}
BASE = "https://odp.met.hu/weather/weather_reports/synoptic/hungary/10_minutes/csv/"
TZ = ZoneInfo("Europe/Budapest")
MISSING = -999.0


def get_bytes(url, timeout=60):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} bei {url}") from None


def decode(b):
    for enc in ("utf-8", "cp1250", "iso-8859-2"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", "replace")


DOC_COLS = ["Time", "StationNumber", "StationName", "Latitude", "Longitude", "Elevation"]


def num(v):
    try:
        x = float(str(v).strip().replace(",", "."))
    except ValueError:
        return None
    return None if x <= MISSING + 0.5 else x


def parse_csv(text):
    """Zeilen als dicts. Kopfzeile = erste Zeile mit 'StationNumber'; Felder werden von Leerzeichen befreit."""
    lines = [l for l in text.splitlines() if l.strip()]
    head = None
    for i, l in enumerate(lines):
        if re.search(r"StationNumber", l, re.I):
            head = [c.strip() for c in l.split(";")]
            lines = lines[i + 1:]
            break
    if head is None:
        raise RuntimeError("Kopfzeile nicht gefunden")
    rows = []
    for l in lines:
        if l.startswith("#"):
            continue
        f = [c.strip() for c in l.split(";")]
        if len(f) < 6:
            continue
        rows.append(dict(zip(head, f)))
    return rows


def read_zip(b):
    z = zipfile.ZipFile(io.BytesIO(b))
    name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    return parse_csv(decode(z.read(name)))


def ts(s):
    s = re.sub(r"\D", "", str(s))
    return datetime.strptime(s[:12], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


def stationen():
    now = datetime.now(timezone.utc)
    listing = decode(get_bytes(BASE))
    files = sorted(set(re.findall(r"HABP_10M_SYNOP_(\d{14})\.csv\.zip", listing)))
    want = [f for f in files if datetime.strptime(f, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc) >= now - timedelta(hours=24, minutes=20)]
    if not want:
        want = files[-1:]
    serien, fehler = {}, 0
    for f in want:
        try:
            rows = read_zip(get_bytes(f"{BASE}HABP_10M_SYNOP_{f}.csv.zip", 40))
        except Exception:
            fehler += 1
            continue
        for r in rows:
            sid = r.get("StationNumber")
            if not sid:
                continue
            try:
                t = ts(r.get("Time"))
            except ValueError:
                continue
            s = serien.setdefault(sid, {"meta": r, "rows": {}})
            s["meta"] = r
            s["rows"][t] = r
    if not serien:
        raise RuntimeError(f"keine Messwerte ({len(want)} Dateien, {fehler} Fehler)")

    mitternacht = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    out = []
    for sid, s in serien.items():
        m = s["meta"]
        lat, lon = num(m.get("Latitude")), num(m.get("Longitude"))
        if lat is None or lon is None:
            continue
        reihe = sorted(s["rows"].items())
        letzte = reihe[-1][0]
        if now - letzte > timedelta(hours=3):
            continue
        st = {"id": sid, "name": m.get("StationName"), "lat": lat, "lon": lon, "hoehe": num(m.get("Elevation")), "at": iso(letzte)}

        def latest(key, maxage=timedelta(minutes=70)):
            for t, r in reversed(reihe):
                if now - t > maxage:
                    return None, None
                v = num(r.get(key))
                if v is not None:
                    return v, t
            return None, None

        for key, name in (("t", "t"), ("u", "rh"), ("p", "p"), ("fs", "wind"), ("fsd", "wdir"), ("fx", "boe"),
                          ("v", "sicht"), ("sg", "gamma"), ("suv", "uv"), ("sr", "glob"), ("tviz", "wasser")):
            v, t = latest(key)
            if v is not None:
                st[name] = round(v, 2)
                if key == "t":
                    st["t_at"] = iso(t)
        # Wind in km/h wie in der App (HungaroMet liefert m/s)
        for k in ("wind", "boe"):
            if k in st:
                st[k] = round(st[k] * 3.6, 1)

        def extrem(stunden, key_lo, key_hi):
            lo = hi = None
            for t, r in reihe:
                if now - t > timedelta(hours=stunden):
                    continue
                a = num(r.get(key_lo))
                b = num(r.get(key_hi))
                tt = num(r.get("t"))
                a = a if a is not None else tt
                b = b if b is not None else tt
                if a is not None and (lo is None or a < lo[0]):
                    lo = (a, t)
                if b is not None and (hi is None or b > hi[0]):
                    hi = (b, t)
            return lo, hi

        for h, sfx in ((12, ""), (24, "24")):
            lo, hi = extrem(h, "tn", "tx")
            if lo:
                st["min" + sfx], st["min" + sfx + "_at"] = round(lo[0], 1), iso(lo[1])
            if hi:
                st["max" + sfx], st["max" + sfx + "_at"] = round(hi[0], 1), iso(hi[1])

        regen = [(t, num(r.get("r"))) for t, r in reihe]
        regen = [(t, v) for t, v in regen if v is not None]
        if regen:
            st["regen_heute"] = round(sum(v for t, v in regen if t > mitternacht), 1)
            st["regen_1h"] = round(sum(v for t, v in regen if now - t <= timedelta(minutes=60)), 1)
            st["regen_24h"] = round(sum(v for t, v in regen), 1)
        g = [num(r.get("sg")) for t, r in reihe]
        g = [v for v in g if v is not None]
        if g and "gamma" in st:
            st["gamma_mittel24"] = round(sum(g) / len(g), 1)
            st["gamma_stunden"] = [round(v, 1) for v in g[-144::6]]
        out.append(st)
    out.sort(key=lambda x: x["name"] or "")
    return {"stationen": out, "dateien": len(want), "dateifehler": fehler}


METEOALARM = "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-hungary"


def local(tag):
    return tag.rsplit("}", 1)[-1]


def warnungen():
    root = ET.fromstring(get_bytes(METEOALARM))
    out = []
    for e in root.iter():
        if local(e.tag) != "entry":
            continue
        d = {}
        for c in e.iter():
            k = local(c.tag)
            if k in ("title", "areaDesc", "event", "severity", "urgency", "certainty", "onset", "effective", "expires",
                     "awareness_level", "awareness_type", "headline", "identifier", "geocode"):
                txt = (c.text or "").strip()
                if txt and k not in d:
                    d[k] = txt
            if k == "link" and c.get("href") and "link" not in d:
                d["link"] = c.get("href")
        if d:
            out.append(d)
    return out


def main():
    data = {"updated": datetime.now(timezone.utc).isoformat(), "quelle": "HungaroMet Nonprofit Zrt. (odp.met.hu), MeteoAlarm", "errors": {}}
    try:
        old = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        old = {}
    for key, fn in (("messnetz", stationen), ("warnungen", warnungen)):
        try:
            data[key] = fn()
        except Exception as e:
            data["errors"][key] = str(e)[:300]
            if key in old:
                data[key] = old[key]
            print(f"{key}: {e}", file=sys.stderr)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    n = len((data.get("messnetz") or {}).get("stationen", []))
    print(f"hu.json: {n} Stationen, {len(data.get('warnungen') or [])} Warnungen, Fehler: {list(data['errors'])}")


if __name__ == "__main__":
    main()
