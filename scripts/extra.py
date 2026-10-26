"""Holt Zusatzdaten fuer die Wetterseite und schreibt sie nach extra.json:
- UV-Index-Vorhersage des DWD (Stadt in der Naehe)
- Pollenflug-Gefahrenindex des DWD (Teilregion mit dem Bayerischen Wald)
- Kp-Index (Polarlicht) des NOAA Space Weather Prediction Center
Jede Quelle ist unabhaengig: faellt eine aus, bleiben die anderen erhalten."""
import json, os, urllib.request
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
            return {"city": c, "forecast": r.get("forecast", {}), "last_update": d.get("last_update"),
                    "cities": sorted(by)}
    return {"city": None, "cities": sorted(by), "last_update": d.get("last_update")}


def pollen():
    d = get("https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json")
    rows = d.get("content", [])
    pick = None
    for r in rows:
        if "Wald" in str(r.get("partregion_name", "")) and r.get("region_id") == 120:
            pick = r
    if not pick:
        pick = next((r for r in rows if r.get("region_id") == 120), None)
    return {"region": (pick or {}).get("partregion_name") or (pick or {}).get("region_name"),
            "pollen": (pick or {}).get("Pollen", {}), "legend": d.get("legend", {}),
            "last_update": d.get("last_update"), "next_update": d.get("next_update")}


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
    for name, fn in [("uv", uv), ("pollen", pollen), ("kp", kp)]:
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
