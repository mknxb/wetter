"""Archiv fuer die Wetterseite (Zweig `daten`, Ordner wird als Argument uebergeben).

Schreibt:
- tage/<ort>.csv        Tageswerte seit 1991 der naechsten DWD-Klimastation (Temperatur, Regen,
                        Sonne, Schnee, Wind, Feuchte), taeglich aus den DWD-Tageswerten (KL)
- stationen.json        welche DWD-Station zu welchem Ort gehoert
- bayern-jahre.csv      DWD-Gebietsmittel Bayern, Jahresmitteltemperatur seit 1881 (Waermestreifen)
- pegel/YYYY-MM.csv     stuendliche Pegelwerte aus pegel.json (eigenes Archiv)
- pegel-tage.csv        Tagesmittel und -maximum je Pegel
- odl/<kenn>.csv        BfS-Tagesmittel der Ortsdosisleistung je Sonde
- odl-aktuell.json      je Ort die naechsten Sonden mit Stundenwert, 7-Tage-Stundenverlauf, 7-Tage-Mittel,
                        dazu unter "cz" die naechsten tschechischen Sonden (EURDEP)
- odl-cz/<id>.csv       eigene Mitschrift der tschechischen Stundenwerte (EURDEP liefert nur den letzten Wert)
- odl/<id>.csv          auch fuer tschechische Sonden: Tagesmittel aus der eigenen Mitschrift
- status.json           Zeitpunkte der letzten Laeufe, Fehler je Teil

Jeder Teil ist unabhaengig; ein Fehler in einem Teil laesst die anderen weiterlaufen.
"""
import csv, io, json, math, os, re, sys, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import date, datetime, timedelta, timezone

OUT = sys.argv[1] if len(sys.argv) > 1 else "daten"
UA = {"User-Agent": "wetter-bayerwald (privat, GitHub Pages)"}
ORTE = {
    "blaibach":   ("Blaibach", 49.1636, 12.8086),
    "koetzting":  ("Bad Kötzting", 49.1767, 12.8547),
    "cham":       ("Cham", 49.2183, 12.6650),
    "furth":      ("Furth im Wald", 49.3097, 12.8400),
    "arber":      ("Großer Arber", 49.1125, 13.1350),
    "zwiesel":    ("Zwiesel", 49.0236, 13.2312),
    "regen":      ("Regen", 48.9700, 13.1270),
    "deggendorf": ("Deggendorf", 48.8353, 12.9644),
}
SEIT = "1991-01-01"
KL = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/"
RR = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/more_precip/"
REG = "https://opendata.dwd.de/climate_environment/CDC/regional_averages_DE/annual/air_temperature_mean/regional_averages_tm_year.txt"
BFS = "https://www.imis.bfs.de/ogc/opendata/ows"
NOW = datetime.now(timezone.utc)


def get_bytes(url, timeout=120):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} bei {url}") from None


def get_json(url):
    return json.loads(get_bytes(url).decode("utf-8", "replace"))


def km(a, b, c, d):
    r = math.pi / 180
    x = (d - b) * r * math.cos((a + c) / 2 * r)
    y = (c - a) * r
    return math.hypot(x, y) * 6371


def path(*p):
    full = os.path.join(OUT, *p)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    return full


def load_json(p, default):
    try:
        return json.load(open(path(p), encoding="utf-8"))
    except Exception:
        return default


def save_json(p, data):
    json.dump(data, open(path(p), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------- DWD-Tageswerte je Ort
def parse_stations(txt):
    out = {}
    for line in txt.splitlines():
        if not line[:5].isdigit():
            continue
        p = line.split()
        try:
            out[p[0]] = {"id": p[0], "von": p[1], "bis": p[2], "hoehe": float(p[3]),
                         "lat": float(p[4]), "lon": float(p[5]), "name": " ".join(p[6:-2])}
        except (ValueError, IndexError):
            continue
    return out


def parse_produkt(raw):
    rows = list(csv.reader(io.StringIO(raw.decode("latin-1")), delimiter=";"))
    head = [h.strip() for h in rows[0]]
    ix = {k: head.index(k) for k in head}
    want = [("tmin", "TNK"), ("tmax", "TXK"), ("tmit", "TMK"), ("regen", "RSK"), ("sonne", "SDK"),
            ("schnee", "SHK_TAG"), ("boe", "FX"), ("wind", "FM"), ("feuchte", "UPM")]
    out = {}
    for r in rows[1:]:
        try:
            ds = r[ix["MESS_DATUM"]].strip()
        except (IndexError, KeyError):
            continue
        d = f"{ds[0:4]}-{ds[4:6]}-{ds[6:8]}"
        if d < SEIT:
            continue
        rec = {}
        for k, col in want:
            try:
                v = float(r[ix[col]])
            except (ValueError, IndexError, KeyError):
                v = None
            if v is not None and v <= -999:
                v = None
            if v is not None and col in ("FX", "FM"):
                v = round(v * 3.6, 1)          # m/s -> km/h
            rec[k] = v
        out[d] = rec
    return out


def zip_produkt(url):
    z = zipfile.ZipFile(io.BytesIO(get_bytes(url, 300)))
    name = next(n for n in z.namelist() if n.startswith("produkt_klima_tag"))
    return parse_produkt(z.read(name))


def zip_regen(url):
    z = zipfile.ZipFile(io.BytesIO(get_bytes(url, 300)))
    name = next(n for n in z.namelist() if n.startswith("produkt_nieder_tag"))
    rows = list(csv.reader(io.StringIO(z.read(name).decode("latin-1")), delimiter=";"))
    head = [h.strip() for h in rows[0]]
    i_d, i_r, i_s = head.index("MESS_DATUM"), head.index("RS"), head.index("SH_TAG")
    out = {}
    for r in rows[1:]:
        ds = r[i_d].strip()
        d = f"{ds[0:4]}-{ds[4:6]}-{ds[6:8]}"
        if d < SEIT:
            continue
        def val(i):
            try:
                v = float(r[i])
            except (ValueError, IndexError):
                return None
            return None if v <= -999 else v
        out[d] = {"regen": val(i_r), "schnee": val(i_s)}
    return out


def pick(stations, have, hist_files, lat, lon, ort, frisch, maxkm):
    cands = []
    for s in stations.values():
        if s["id"] not in have or s["bis"] < frisch:
            continue
        d = km(lat, lon, s["lat"], s["lon"])
        if d > maxkm:
            continue
        lang = s["von"] <= "19910101" and s["id"] in hist_files
        dh = abs(s["hoehe"] - (1400 if ort == "arber" else 450))
        score = d + (0 if lang else 12) + dh / 40
        cands.append((score, d, s))
    cands.sort(key=lambda c: c[0])
    return (cands[0][2], cands[0][1]) if cands else (None, None)


COLS = ["tmin", "tmax", "tmit", "regen", "sonne", "schnee", "boe", "wind", "feuchte"]


def fmt(v):
    return "" if v is None else (f"{v:.1f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v))


def write_tage(ort, data):
    with open(path("tage", f"{ort}.csv"), "w", encoding="utf-8", newline="") as f:
        f.write("datum;" + ";".join(COLS) + "\n")
        for d in sorted(data):
            f.write(d + ";" + ";".join(fmt(data[d].get(k)) for k in COLS) + "\n")


def read_tage(ort):
    p = path("tage", f"{ort}.csv")
    if not os.path.exists(p):
        return {}
    out = {}
    with open(p, encoding="utf-8") as f:
        r = csv.reader(f, delimiter=";")
        head = next(r)
        for row in r:
            out[row[0]] = {k: (float(v) if v != "" else None) for k, v in zip(head[1:], row[1:])}
    return out


def teil_tage(status):
    st = status.setdefault("tage", {})
    today = NOW.date().isoformat()
    if st.get("tag") == today and st.get("v") == 2 and all(os.path.exists(path("tage", f"{o}.csv")) for o in ORTE):
        return "heute schon aktuell"
    frisch = (NOW.date() - timedelta(days=12)).strftime("%Y%m%d")
    have = set(re.findall(r"tageswerte_KL_(\d{5})_akt\.zip", get_bytes(KL + "recent/").decode("latin-1")))
    hist = {m.group(1): m.group(0) for m in re.finditer(r"tageswerte_KL_(\d{5})_\d{8}_\d{8}_hist\.zip", get_bytes(KL + "historical/").decode("latin-1"))}
    stations = parse_stations(get_bytes(KL + "recent/KL_Tageswerte_Beschreibung_Stationen.txt").decode("latin-1"))
    rhave = set(re.findall(r"tageswerte_RR_(\d{5})_akt\.zip", get_bytes(RR + "recent/").decode("latin-1")))
    rhist = {m.group(1): m.group(0) for m in re.finditer(r"tageswerte_RR_(\d{5})_\d{8}_\d{8}_hist\.zip", get_bytes(RR + "historical/").decode("latin-1"))}
    rstations = parse_stations(get_bytes(RR + "recent/RR_Tageswerte_Beschreibung_Stationen.txt").decode("latin-1"))
    zuordnung, cache, rcache = {}, {}, {}
    for ort, (name, lat, lon) in ORTE.items():
        s, d = pick(stations, have, hist, lat, lon, ort, frisch, 60)
        if not s:
            continue
        r, rd = pick(rstations, rhave, rhist, lat, lon, ort, frisch, 15)
        z = {"id": s["id"], "name": s["name"], "hoehe": s["hoehe"], "km": round(d, 1), "seit": s["von"], "lat": s["lat"], "lon": s["lon"]}
        if r:
            z["regen"] = {"id": r["id"], "name": r["name"], "hoehe": r["hoehe"], "km": round(rd, 1), "seit": r["von"]}
        old_ok = st.get("v") == 2 and st.get("station", {}).get(ort) == s["id"] + "/" + (r["id"] if r else "")
        key = s["id"]
        if key not in cache:
            data = {}
            if old_ok:
                data = read_tage(ort)
            if not data and s["id"] in hist:
                data.update(zip_produkt(KL + "historical/" + hist[s["id"]]))
            for dd, rec in zip_produkt(KL + f"recent/tageswerte_KL_{s['id']}_akt.zip").items():
                data[dd] = rec
            cache[key] = data
        data = {dd: dict(rec) for dd, rec in cache[key].items()}
        if r:
            if r["id"] not in rcache:
                rr = {}
                if r["id"] in rhist and not old_ok:
                    rr.update(zip_regen(RR + "historical/" + rhist[r["id"]]))
                rr.update(zip_regen(RR + f"recent/tageswerte_RR_{r['id']}_akt.zip"))
                rcache[r["id"]] = rr
            for dd, rec in rcache[r["id"]].items():
                row = data.setdefault(dd, {})
                if rec["regen"] is not None:
                    row["regen"] = rec["regen"]
                if rec["schnee"] is not None:
                    row["schnee"] = rec["schnee"]
        write_tage(ort, data)
        z["bis"] = max(data) if data else None
        z["tage"] = len(data)
        zuordnung[ort] = z
        st.setdefault("station", {})[ort] = s["id"] + "/" + (r["id"] if r else "")
    save_json("stationen.json", zuordnung)
    st["tag"] = today
    st["v"] = 2
    return "; ".join(f"{o}: {z['name']} ({z['km']} km){' + Regen ' + z['regen']['name'] if z.get('regen') else ''}" for o, z in zuordnung.items())


def teil_bayern(status):
    st = status.setdefault("bayern", {})
    if st.get("tag") == NOW.date().isoformat() and os.path.exists(path("bayern-jahre.csv")):
        return "heute schon aktuell"
    txt = get_bytes(REG).decode("latin-1")
    lines = [l for l in txt.splitlines() if ";" in l]
    head_i = next(i for i, l in enumerate(lines) if l.lower().startswith("jahr"))
    head = [h.strip() for h in lines[head_i].split(";")]
    ib = head.index("Bayern")
    rows = []
    for l in lines[head_i + 1:]:
        p = [x.strip() for x in l.split(";")]
        try:
            rows.append((int(p[0]), float(p[ib])))
        except (ValueError, IndexError):
            continue
    with open(path("bayern-jahre.csv"), "w", encoding="utf-8") as f:
        f.write("jahr;tmit\n" + "".join(f"{y};{v:.2f}\n" for y, v in rows))
    st["tag"] = NOW.date().isoformat()
    return f"{len(rows)} Jahre bis {rows[-1][0]}"


# ---------------------------------------------------------------- Pegel (eigenes Archiv)
def teil_pegel(status):
    pj = json.load(open("pegel.json", encoding="utf-8"))
    neu = 0
    for s in pj.get("stations", []):
        for t, lvl in s.get("hist", []):
            ts = t[:16]
            mon = ts[:7]
            p = path("pegel", f"{mon}.csv")
            key = f"{ts};{s['id']}"
            seen = status.setdefault("pegel_seen", {})
            if seen.get(mon) is None:
                seen[mon] = []
                if os.path.exists(p):
                    with open(p, encoding="utf-8") as f:
                        next(f, None)
                        seen[mon] = [";".join(l.split(";")[:2]) for l in f]
            if key in seen[mon]:
                continue
            new_file = not os.path.exists(p)
            with open(p, "a", encoding="utf-8") as f:
                if new_file:
                    f.write("zeit;id;stand_cm\n")
                f.write(f"{key};{lvl}\n")
            seen[mon].append(key)
            neu += 1
    status.pop("pegel_seen", None)
    # Tageswerte neu berechnen (klein, schnell)
    tage = {}
    pdir = path("pegel", "x")[:-2]
    for fn in sorted(os.listdir(pdir)):
        if not fn.endswith(".csv"):
            continue
        with open(os.path.join(pdir, fn), encoding="utf-8") as f:
            next(f, None)
            for l in f:
                ts, pid, v = l.strip().split(";")
                try:
                    v = float(v)
                except ValueError:
                    continue
                k = (ts[:10], pid)
                a = tage.setdefault(k, [0, 0.0, -1e9, 1e9])
                a[0] += 1; a[1] += v; a[2] = max(a[2], v); a[3] = min(a[3], v)
    with open(path("pegel-tage.csv"), "w", encoding="utf-8") as f:
        f.write("datum;id;mittel;max;min;werte\n")
        for (d, pid), (n, s, mx, mn) in sorted(tage.items()):
            f.write(f"{d};{pid};{s / n:.1f};{mx:g};{mn:g};{n}\n")
    # Meldestufen-Grenzen der Haupt-Pegel (einmal pro Tag, tolerant)
    ms = load_json("pegel-meldestufen.json", {})
    if status.setdefault("ms", {}).get("tag") != NOW.date().isoformat():
        for s in pj.get("stations", []):
            if s["id"] not in KEY_PEGEL or not s.get("url"):
                continue
            try:
                html = get_bytes(s["url"], 60).decode("utf-8", "replace")
                txt = re.sub(r"<[^>]+>", " ", html)
                txt = re.sub(r"\s+", " ", txt)
                vals = {}
                for n in "1234":
                    m = re.search(rf"Meldestufe\s*{n}\D{{0,40}}?(\d{{2,4}})\s*cm", txt)
                    if m:
                        vals[n] = int(m.group(1))
                m = re.search(r"\bMW\b\D{0,20}?(\d{2,4})\s*cm", txt)
                if m:
                    vals["MW"] = int(m.group(1))
                if vals:
                    ms[s["id"]] = vals
            except Exception as e:
                ms.setdefault("_fehler", {})[s["id"]] = str(e)[:120]
        save_json("pegel-meldestufen.json", ms)
        status["ms"]["tag"] = NOW.date().isoformat()
    return f"{neu} neue Stundenwerte, {len(tage)} Pegeltage, Meldestufen fuer {len([k for k in ms if not k.startswith('_')])} Pegel"


KEY_PEGEL = {"15228008", "15202300", "15204000", "15246000", "15243001", "15210206", "15214003",
             "15212700", "15212008", "15221009", "10081004"}


# ---------------------------------------------------------------- Strahlung (BfS)
def bfs(params):
    q = {"service": "WFS", "version": "1.1.0", "request": "GetFeature", "outputFormat": "application/json", **params}
    return get_json(BFS + "?" + urllib.parse.urlencode(q))


def teil_odl(status):
    st = status.setdefault("odl", {})
    latest = bfs({"typeName": "opendata:odlinfo_odl_1h_latest"})
    sonden = []
    for f in latest.get("features", []):
        p = f.get("properties", {})
        lon, lat = (f.get("geometry") or {}).get("coordinates", [None, None])[:2]
        if lat is None or p.get("value") is None:
            continue
        sonden.append({"kenn": p.get("kenn"), "name": p.get("name"), "lat": lat, "lon": lon,
                       "hoehe": p.get("height_above_sea"), "wert": p.get("value"), "ende": p.get("end_measure")})
    aktuell = {"stand": NOW.isoformat(), "orte": {}}
    benoetigt = {}
    for ort, (name, lat, lon) in ORTE.items():
        near = sorted(sonden, key=lambda s: km(lat, lon, s["lat"], s["lon"]))[:3]
        liste = []
        for s in near:
            s2 = dict(s, km=round(km(lat, lon, s["lat"], s["lon"]), 1))
            liste.append(s2)
            benoetigt[s["kenn"]] = s
        aktuell["orte"][ort] = liste
    # Stundenverlauf 7 Tage je benoetigter Sonde
    for kenn, s in benoetigt.items():
        try:
            ts = bfs({"typeName": "opendata:odlinfo_timeseries_odl_1h", "viewparams": f"kenn:{kenn}",
                      "sortBy": "end_measure D", "maxFeatures": "168"})
            pts = sorted(((f["properties"]["end_measure"], f["properties"]["value"]) for f in ts.get("features", [])
                          if f["properties"].get("value") is not None))
            s["stunden"] = [[t[:16], v] for t, v in pts]
            vals = [v for _, v in pts]
            s["mittel7"] = round(sum(vals) / len(vals), 4) if vals else None
        except Exception as e:
            s["fehler"] = str(e)[:120]
    for ort, liste in aktuell["orte"].items():
        for s in liste:
            s.update({k: benoetigt[s["kenn"]].get(k) for k in ("stunden", "mittel7", "fehler") if k in benoetigt[s["kenn"]]})
    try:
        ncz = teil_cz(aktuell, st)
        st.pop("cz_fehler", None)
    except Exception as e:
        ncz = 0
        st["cz_fehler"] = f"{type(e).__name__}: {e}"[:200]
    save_json("odl-aktuell.json", aktuell)
    # Tageswerte (lange Reihe) einmal pro Tag
    if st.get("tag") != NOW.date().isoformat():
        for kenn in benoetigt:
            p = path("odl", f"{kenn}.csv")
            have = {}
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    next(f, None)
                    for l in f:
                        d, v = l.strip().split(";")
                        have[d] = v
            try:
                ts = bfs({"typeName": "opendata:odlinfo_timeseries_odl_24h", "viewparams": f"kenn:{kenn}",
                          "sortBy": "end_measure D", "maxFeatures": "1000" if have else "4000"})
                for f in ts.get("features", []):
                    pr = f["properties"]
                    if pr.get("value") is None:
                        continue
                    d = (datetime.fromisoformat(pr["end_measure"].replace("Z", "+00:00")) - timedelta(hours=1)).date().isoformat()
                    have[d] = f"{pr['value']:.4f}"
            except Exception as e:
                st.setdefault("fehler", {})[kenn] = str(e)[:120]
                continue
            with open(p, "w", encoding="utf-8") as f:
                f.write("datum;usvh\n" + "".join(f"{d};{v}\n" for d, v in sorted(have.items())))
        st["tag"] = NOW.date().isoformat()
    return f"{len(sonden)} Sonden, {len(benoetigt)} im Archiv, {ncz} in Tschechien"


# ---------------------------------------------------------------- Strahlung Tschechien (EURDEP, eigene Mitschrift)
def _num(v):
    if isinstance(v, str):
        v = v.replace(",", ".")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def eurdep_row(f):
    p = f.get("properties") or {}
    lon, lat = ((f.get("geometry") or {}).get("coordinates") or [None, None])[:2]
    sid = str(p.get("id") or p.get("locality_code") or p.get("code") or f.get("id") or "")
    cc = str(p.get("country") or p.get("country_code") or re.sub(r"^[^A-Z]*", "", sid)[:2]).upper()
    v = _num(p.get("value", p.get("val", p.get("dose_rate", p.get("value_nsv")))))
    unit = str(p.get("unit") or "")
    if v is not None and (re.search("nSv", unit, re.I) or v > 5):
        v = v / 1000
    name = str(p.get("name") or p.get("locality_name") or p.get("site_name") or p.get("locality") or sid)
    name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
    end = p.get("end_measure") or p.get("end_time") or p.get("endtime") or p.get("time") or p.get("end")
    key = re.sub(r"[^A-Za-z0-9_-]", "", sid) or re.sub(r"[^A-Za-z0-9]", "", name)
    return {"kenn": "CZ_" + key, "name": name, "lat": lat, "lon": lon, "wert": round(v, 4) if v is not None else None,
            "ende": end, "cc": cc}


def teil_cz(aktuell, st):
    fc = bfs({"typeName": "opendata:eurdep_latestValue"})
    feats = fc.get("features", [])
    if feats:
        st["cz_felder"] = sorted((feats[0].get("properties") or {}).keys())[:40]
    sonden = {}
    for f in feats:
        s = eurdep_row(f)
        if s["cc"] != "CZ" or s["wert"] is None or s["lat"] is None:
            continue
        if min(km(lat, lon, s["lat"], s["lon"]) for _, lat, lon in ORTE.values()) > 90:
            continue
        o = sonden.get(s["kenn"])
        if not o or str(s["ende"] or "") > str(o["ende"] or ""):
            sonden[s["kenn"]] = s
    grenze = (NOW - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")
    for kenn, s in sonden.items():
        p = path("odl-cz", f"{kenn[3:]}.csv")
        rows = {}
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                next(f, None)
                for l in f:
                    t, v = l.strip().split(";")
                    rows[t] = v
        t = str(s["ende"] or NOW.isoformat())[:16]
        rows[t] = f"{s['wert']:.4f}"
        with open(p, "w", encoding="utf-8") as f:
            f.write("zeit;usvh\n" + "".join(f"{k};{v}\n" for k, v in sorted(rows.items())))
        stunden = [[k, float(v)] for k, v in sorted(rows.items()) if k >= grenze]
        s["stunden"] = stunden
        s["mittel7"] = round(sum(v for _, v in stunden) / len(stunden), 4) if stunden else None
        s["seit"] = min(rows)[:10]
        # Tagesmittel (nur abgeschlossene Tage, UTC) fuer die lange Reihe
        tage = {}
        for k, v in rows.items():
            tage.setdefault(k[:10], []).append(float(v))
        heute = NOW.date().isoformat()
        with open(path("odl", f"{kenn}.csv"), "w", encoding="utf-8") as f:
            f.write("datum;usvh\n" + "".join(f"{d};{sum(v) / len(v):.4f}\n" for d, v in sorted(tage.items()) if d < heute))
    aktuell["cz"] = {}
    for ort, (name, lat, lon) in ORTE.items():
        near = sorted(sonden.values(), key=lambda s: km(lat, lon, s["lat"], s["lon"]))[:4]
        aktuell["cz"][ort] = [dict(s, km=round(km(lat, lon, s["lat"], s["lon"]), 1)) for s in near
                              if km(lat, lon, s["lat"], s["lon"]) < 90]
    return len(sonden)


def main():
    status = load_json("status.json", {})
    status["lauf"] = NOW.isoformat()
    status["fehler"] = {}
    for name, fn in [("tage", teil_tage), ("bayern", teil_bayern), ("pegel", teil_pegel), ("odl", teil_odl)]:
        try:
            status.setdefault("ergebnis", {})[name] = fn(status)
            print(name, "ok:", status["ergebnis"][name])
        except Exception as e:
            status["fehler"][name] = f"{type(e).__name__}: {e}"[:300]
            print(name, "Fehler:", e)
    save_json("status.json", status)


if __name__ == "__main__":
    main()
