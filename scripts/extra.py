"""Holt Zusatzdaten fuer die Wetterseite und schreibt sie nach extra.json:
- UV-Index-Vorhersage des DWD (Stadt in der Naehe)
- Pollenflug-Gefahrenindex des DWD (Teilregion mit dem Bayerischen Wald)
- Kp-Index (Polarlicht) des NOAA Space Weather Prediction Center
- Biowetter des DWD (Zone mit Ostbayern)
- Schneehoehe der DWD-Station Grosser Arber (Tageswerte, Stand Vortag)
Jede Quelle ist unabhaengig: faellt eine aus, bleiben die anderen erhalten."""
import csv, io, json, os, re, urllib.request, zipfile
from datetime import datetime, timezone

OUT = "extra.json"
UA = {"User-Agent": "wetter-bayerwald (privat, GitHub Pages)"}
UV_CITIES = ["Regensburg", "Passau", "Straubing", "Weiden", "Deggendorf", "Nürnberg", "München"]


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def uv():
    d = get("https://opendata.dwd.de/climate_environment/health/alerts/uvi.json")
    rows = d.get("content", [])
    by = {r.get("city"): r for r in rows}
    for c in UV_CITIES:
        if c in by:
            r = by[c]
            arber = by.get("Großer Arber", {}).get("forecast")
            return {"city": c, "forecast": r.get("forecast", {}), "arber": arber, "last_update": d.get("last_update")}
    return {"city": None, "cities": sorted(by), "last_update": d.get("last_update")}


def pollen():
    d = get("https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json")
    rows = d.get("content", [])
    pick = None
    for r in rows:
        n = str(r.get("partregion_name", ""))
        # "Bay. Wald" gehoert dazu, "o. Bayr. Wald" (ohne Bayerischen Wald) nicht
        if r.get("region_id") == 120 and re.search(r"Bayr?\. ?Wald", n) and not re.search(r"o\. ?Bayr?\. ?Wald", n):
            pick = r
    if not pick:
        pick = next((r for r in rows if r.get("region_id") == 120), None)
    return {"region": (pick or {}).get("partregion_name") or (pick or {}).get("region_name"),
            "pollen": (pick or {}).get("Pollen", {}), "legend": d.get("legend", {}),
            "last_update": d.get("last_update"), "next_update": d.get("next_update"),
            "regions": [r.get("partregion_name") for r in rows if r.get("region_id") == 120]}


def get_bytes(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
        return r.read()


BIO_PREFER = re.compile(r"Ostbayern|Bayerischer Wald|Oberpfalz|Niederbayern|Bayern", re.I)


def biowetter():
    d = get("https://opendata.dwd.de/climate_environment/health/alerts/biowetter.json")
    zones = d.get("zone", [])
    pick = None
    for z in zones:
        if BIO_PREFER.search(str(z.get("name", ""))):
            pick = z
            if re.search(r"Ost|Wald|Oberpfalz|Nieder", str(z.get("name", "")), re.I):
                break
    return {"zone": pick, "zones": [{"id": z.get("id"), "name": z.get("name")} for z in zones],
            "last_update": d.get("last_update"), "next_update": d.get("next_update")}


KL = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/recent/"


def snow_arber():
    lst = get_bytes(KL + "KL_Tageswerte_Beschreibung_Stationen.txt").decode("latin-1")
    sid = None
    for line in lst.splitlines():
        if re.search(r"Gro.er Arber", line):
            sid = line.split()[0]
            break
    if not sid:
        raise RuntimeError("Station Grosser Arber nicht in der Liste")
    z = zipfile.ZipFile(io.BytesIO(get_bytes(KL + f"tageswerte_KL_{sid}_akt.zip")))
    name = next(n for n in z.namelist() if n.startswith("produkt_klima_tag"))
    rows = list(csv.reader(io.StringIO(z.read(name).decode("latin-1")), delimiter=";"))
    head = [h.strip() for h in rows[0]]
    i_d, i_s = head.index("MESS_DATUM"), head.index("SHK_TAG")
    series = []
    for r in rows[1:]:
        try:
            v = float(r[i_s])
        except (ValueError, IndexError):
            continue
        if v < 0:
            continue
        ds = r[i_d].strip()
        series.append([f"{ds[0:4]}-{ds[4:6]}-{ds[6:8]}", v])
    return {"station_id": sid, "series": series[-30:]}


def rows_to_dicts(d):
    # NOAA liefert je nach Produkt Liste von Listen (mit Kopfzeile) oder Liste von Objekten
    if d and isinstance(d[0], list):
        head = d[0]
        return [dict(zip(head, r)) for r in d[1:]]
    return d


def kp():
    fc = rows_to_dicts(get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"))
    out = []
    for r in fc:
        t, v = r.get("time_tag"), r.get("kp")
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        out.append({"t": t if str(t).endswith("Z") else str(t).replace(" ", "T") + "Z", "kp": v,
                    "obs": r.get("observed")})
    return {"series": out}


def main():
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            old = {}
    res = {"updated": datetime.now(timezone.utc).isoformat()}
    for name, fn in [("uv", uv), ("pollen", pollen), ("kp", kp), ("bio", biowetter), ("snow", snow_arber)]:
        try:
            res[name] = fn()
        except Exception as e:  # Quelle gerade nicht erreichbar: alten Stand behalten
            print(name, "Fehler:", e)
            if name in old:
                res[name] = old[name]
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("extra.json:", ", ".join(k for k in res if k != "updated"))


if __name__ == "__main__":
    main()
