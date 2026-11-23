"""Holt Daten fuer die Region Ungarn der Wetterseite und schreibt sie nach hu.json:
- 10-Minuten-Messwerte aller Automatikstationen von HungaroMet (odp.met.hu, offene Daten),
  dazu Tiefst-/Hoechstwerte 12 h und 24 h, Regen heute und letzte Stunde, Gamma-Ortsdosisleistung
- Pegel Donau, Balaton und Velencei-to mit Wassertemperatur von hydroinfo.hu (OVF), eigener Verlauf 45 Tage,
  dazu Stundenwerte und Alarmstufen je Pegel von vizugy.hu (OVF, Vízmérce-Seiten); die volle Stundenreihe geht
  nach hu-pegel-roh.json (nicht eingecheckt) und wird von archiv.py ins eigene Archiv uebernommen
- Unwetterwarnungen fuer Ungarn ueber MeteoAlarm (Atom-Feed)
Jede Quelle ist unabhaengig: faellt eine aus, bleibt der Rest erhalten (Fehler unter "errors").
Quelle der Messwerte: HungaroMet Nonprofit Zrt. (Nennung ist Nutzungsbedingung)."""
import csv, html, io, json, re, sys, urllib.error, urllib.request, zipfile
from html.parser import HTMLParser
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
        # Stationsluftdruck vor etwa 3 Stunden (fuer die Drucktendenz)
        p3 = [(abs((now - t) - timedelta(hours=3)), num(r.get("p"))) for t, r in reihe]
        p3 = [x for x in p3 if x[1] is not None and x[0] <= timedelta(minutes=20)]
        if p3 and "p" in st:
            st["p3"] = round(min(p3)[1], 1)
        stunden = [(t, num(r.get("t"))) for t, r in reihe if t.minute == 0]
        st["t_stunden"] = [[iso(t), round(v, 1)] for t, v in stunden if v is not None]
        g = [num(r.get("sg")) for t, r in reihe]
        g = [v for v in g if v is not None]
        if g and "gamma" in st:
            st["gamma_mittel24"] = round(sum(g) / len(g), 1)
            st["gamma_stunden"] = [round(v, 1) for v in g[-144::6]]
        out.append(st)
    out.sort(key=lambda x: x["name"] or "")
    return {"stationen": out, "dateien": len(want), "dateifehler": fehler}


HYDRO = "https://www.hydroinfo.hu/tables/ENG/"
# Pegel, die die App zeigt: Kennung der OVF/hydroinfo-Tabellen -> (Anzeigename, Gewaesser, Breite, Laenge)
PEGEL = {
    "442025": ("Esztergom", "Duna", 47.7970, 18.7410),
    "442527": ("Nagymaros", "Duna", 47.7870, 18.9580),
    "442026": ("Vác", "Duna", 47.7750, 19.1280),
    "442027": ("Budapest (Vigadó tér)", "Duna", 47.4960, 19.0470),
    "442533": ("Budafok", "Duna", 47.4200, 19.0400),
    "442028": ("Dunaújváros", "Duna", 46.9640, 18.9400),
    "442600": ("Balaton (Mittel)", "Balaton", 46.8500, 17.7500),
    "442550": ("Siófok", "Balaton", 46.9090, 18.0480),
    "442633": ("Tihany rév", "Balaton", 46.8930, 17.8920),
    "442632": ("Balatonakali", "Balaton", 46.8820, 17.7520),
    "442558": ("Agárd", "Velencei-tó", 47.1880, 18.5900),
}


class Tabelle(HTMLParser):
    """Sammelt alle Tabellenzeilen als Listen von (Text, Attribute) je Zelle."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell, self.attrs, self.text = [], None, None, None, []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell, self.attrs = [], dict(attrs)
        elif self.cell is not None and tag in ("font", "span", "b") and attrs:
            self.attrs.update({"_" + k: v for k, v in attrs if v})

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append((" ".join("".join(self.cell).split()), self.attrs or {}))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None

    def handle_data(self, d):
        if self.cell is not None:
            self.cell.append(d)
        self.text.append(d)


def tabelle(name):
    p = Tabelle()
    p.feed(decode(get_bytes(HYDRO + name)))
    return p


def ganz(v):
    v = str(v).strip().replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


MONATE_EN = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                         "september", "october", "november", "december"], 1)}


def stichtag(p):
    m = re.search(r"Observed on:\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", " ".join(p.text))
    if m and m.group(2).lower() in MONATE_EN:
        return datetime(int(m.group(3)), MONATE_EN[m.group(2).lower()], int(m.group(1)))
    return datetime.now(TZ).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)


def farbe(attrs):
    s = " ".join(str(v) for v in attrs.values()).lower()
    for k, w in (("purple", "lila"), ("#ff00ff", "lila"), ("red", "rot"), ("#ff0000", "rot"), ("orange", "orange"), ("#ff9900", "orange"),
                 ("#ffa500", "orange"), ("yellow", "gelb"), ("#ffff00", "gelb"), ("blue", "blau"), ("#00ffff", "blau"), ("#0000ff", "blau")):
        if k in s:
            return w
    return None


def gewaesser():
    """Pegel Donau (Fluss-Tabelle) und Seen (Seen-Tabelle) von hydroinfo.hu (OVF).
    Fluss: Kennung, Name, Fluss, Stand gestern frueh/abends, heute frueh, Aenderung 24 h, Abfluss m3/s, Wassertemperatur, Eis.
    See:   Kennung, Name, See, Stand gestern frueh/abends, heute frueh, Aenderung 24 h, Wassertemperatur frueh, Eis."""
    try:
        alt = {g["id"]: g for g in json.load(open(OUT, encoding="utf-8")).get("gewaesser", {}).get("pegel", [])}
    except Exception:
        alt = {}
    out, fehler = [], []
    for datei, see in (("dunhid_a.html", False), ("tohid.html", True)):
        try:
            p = tabelle(datei)
        except Exception as e:
            fehler.append(f"{datei}: {e}")
            continue
        tag = stichtag(p)
        for row in p.rows:
            zellen = [c[0] for c in row]
            if len(zellen) < 8 or not re.fullmatch(r"\d{6}", zellen[0]) or zellen[0] not in PEGEL or any(g["id"] == zellen[0] for g in out):
                continue
            name, wasser, lat, lon = PEGEL[zellen[0]]
            g = {"id": zellen[0], "name": name, "gewaesser": wasser, "lat": lat, "lon": lon, "datum": tag.strftime("%Y-%m-%d"),
                 "stand": ganz(zellen[5]), "gestern_frueh": ganz(zellen[3]), "gestern_abend": ganz(zellen[4]), "aenderung": ganz(zellen[6])}
            if see:
                g["wassertemp"] = ganz(zellen[7])
            else:
                g["abfluss"] = ganz(zellen[7])
                g["wassertemp"] = ganz(zellen[8]) if len(zellen) > 8 else None
            f = farbe(row[5][1])
            if f:
                g["stufe"] = f
            # eigener Verlauf: je Tag Morgen- (07 Uhr) und Abendwert (19 Uhr), 45 Tage
            v = {t: w for t, w in (alt.get(g["id"], {}).get("verlauf") or [])}
            gestern = (tag - timedelta(days=1)).strftime("%Y-%m-%d")
            for t, w in ((f"{gestern}T07", g["gestern_frueh"]), (f"{gestern}T19", g["gestern_abend"]), (f"{g['datum']}T07", g["stand"])):
                if w is not None:
                    v[t] = w
            grenze = (tag - timedelta(days=45)).strftime("%Y-%m-%d")
            g["verlauf"] = sorted([[t, w] for t, w in v.items() if t >= grenze])
            out.append(g)
    if not out:
        raise RuntimeError("; ".join(fehler) or "keine Pegel gefunden")
    ids = {}
    try:
        ids = stundenwerte(out, alt_ids(), fehler)
    except Exception as e:
        fehler.append(f"vizugy: {e}"[:200])
    return {"pegel": out, "fehler": fehler, "vizugy": ids}


# Stundenwerte je Pegel: vizugy.hu, Seite "Vízmérce" (OpGrafikon, OrasIdosor). Die Seiten haben eine GUID je Pegel;
# bekannte stehen hier, die uebrigen werden aus den Links der landesweiten Pegelliste auf derselben Seite ermittelt.
VIZUGY = "https://www.vizugy.hu/?mapModule=OpGrafikon&AllomasVOA={}&mapData=OrasIdosor"
VIZUGY_BEKANNT = {"442550": "164961A4-97AB-11D4-BB62-00508BA24287", "442527": "16496053-97AB-11D4-BB62-00508BA24287"}
VIZUGY_NAMEN = {"442025": ["esztergom"], "442527": ["nagymaros"], "442026": ["vac"], "442027": ["budapest", "budapest vigado ter"],
                "442533": ["budafok", "budapest-budafok", "budapest budafok"], "442028": ["dunaujvaros"], "442550": ["siofok"],
                "442633": ["tihany", "tihany-rev", "tihany rev", "tihanyi rev"], "442632": ["balatonakali"], "442558": ["agard"]}
ROH = "hu-pegel-roh.json"


def alt_ids():
    try:
        return json.load(open(OUT, encoding="utf-8")).get("gewaesser", {}).get("vizugy") or {}
    except Exception:
        return {}


def norm(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", html.unescape(str(t))).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9-]+", " ", t).split())


def vizugy_seite(guid):
    return decode(get_bytes(VIZUGY.format(guid), timeout=30))


def guid_links(seite):
    """Alle Pegel-Links einer vizugy-Seite: normierter Name -> GUID."""
    out = {}
    for g, txt in re.findall(r'<a[^>]+AllomasVOA=([0-9A-Fa-f-]{36})[^>]*>(.*?)</a>', seite, re.S | re.I):
        n = norm(re.sub(r"<[^>]+>", " ", txt))
        if n and n not in out:
            out[n] = g.upper()
    return out


def reihe(seite):
    """Stundenwerte (UTC-Zeit, cm) und Kenndaten (Alarmstufen I-III, LNV, LKV) aus einer Vízmérce-Seite."""
    txt = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", seite)).split())
    werte = {}
    for y, mo, d, h, mi, v in re.findall(r"(\d{4})\.(\d{2})\.(\d{2})\.\s*(\d{2}):(\d{2})\s+(-?\d+(?:[.,]\d+)?)", txt):
        if mi != "00":
            continue
        t = datetime(int(y), int(mo), int(d), int(h), tzinfo=TZ).astimezone(timezone.utc)
        werte[t.strftime("%Y-%m-%dT%H:00")] = float(v.replace(",", "."))
    ms = {}
    for stufe, cm in re.findall(r"\b(I{1,3})\.\s*k[ée]sz[üu]lts[ée]gi szint:\s*(-?\d+)\s*cm", txt):
        ms[str(len(stufe))] = int(cm)
    for k, rx in (("LNV", r"\(LNV\):\s*(-?\d+)"), ("LKV", r"\(LKV\):\s*(-?\d+)")):
        m = re.search(rx, txt)
        if m:
            ms[k] = int(m.group(1))
    return sorted(werte.items()), ms


def stundenwerte(pegel, ids, fehler):
    """Holt je Pegel die Stundenreihe; haengt die letzten 7 Tage als "stunden" an, den aktuellen Wert als "aktuell"."""
    ids = {**VIZUGY_BEKANNT, **ids}
    seiten, links, roh, fehlschlaege = {}, {}, {}, 0
    if any(g["id"] in VIZUGY_NAMEN and g["id"] not in ids for g in pegel):
        for guid in list(dict.fromkeys(ids.values()))[:3]:   # die Pegelliste steht auf jeder Vízmérce-Seite
            try:
                seiten[guid] = vizugy_seite(guid)
                links = guid_links(seiten[guid])
            except Exception as e:
                fehler.append(f"vizugy Liste: {e}"[:160])
            if links:
                break
        for g in pegel:
            for n in VIZUGY_NAMEN.get(g["id"], []):
                if g["id"] not in ids and n in links:
                    ids[g["id"]] = links[n]
    grenze = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:00")
    for g in pegel:
        guid = ids.get(g["id"])
        if not guid or fehlschlaege >= 3:
            continue
        try:
            werte, ms = reihe(seiten.get(guid) or vizugy_seite(guid))
        except Exception as e:
            fehlschlaege += 1
            fehler.append(f"vizugy {g['name']}: {e}"[:160])
            continue
        if ms:
            g["ms"] = ms
        if werte:
            roh[g["id"]] = werte
            g["stunden"] = [[t, v] for t, v in werte if t >= grenze]
            g["aktuell"], g["aktuell_zeit"] = werte[-1][1], werte[-1][0] + ":00Z"
    try:
        with open(ROH, "w", encoding="utf-8") as f:
            json.dump(roh, f, separators=(",", ":"))
    except OSError:
        pass
    return ids


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
    for key, fn in (("messnetz", stationen), ("gewaesser", gewaesser), ("warnungen", warnungen)):
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
    print(f"hu.json: {n} Stationen, {len((data.get('gewaesser') or {}).get('pegel', []))} Pegel, {len(data.get('warnungen') or [])} Warnungen, Fehler: {list(data['errors'])}")


if __name__ == "__main__":
    main()
