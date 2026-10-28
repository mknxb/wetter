# IT-Dokumentation Wetter Bayerwald

Stand 28.10.2026 · Matthias Brem · Kopie der IT-Dokumentation aus Claude Docs (Architekturdiagramm nur dort)

## Überblick

Die Wetter-App „Wetter Bayerwald“ ist eine statische Web-Seite ohne eigenen Server. Sie fragt Wetter-, Radar-, Strahlungs- und Pegeldaten aus öffentlichen Quellen live im Browser ab und startet mit Blaibach oder dem per Stern gemerkten Ort. Eine Kopie dieser Doku liegt im Repository als DOKUMENTATION.md.

| Eigenschaft | Wert |
| --- | --- |
| Live-Seite | [mknxb.github.io/wetter/](https://mknxb.github.io/wetter/) |
| Testseite | [mknxb.github.io/wetter/test/](https://mknxb.github.io/wetter/test/) |
| Repository | [github.com/mknxb/wetter](https://github.com/mknxb/wetter), öffentlich |
| Eigentümer | Matthias Brem, GitHub-Konto `mknxb` (vorher `matthiasbrem-create`) |
| Hosting | GitHub Pages, Zweig `main`, Ordner `/` |
| Nutzung | privat, als Web-Seite und als installierbare App (PWA) auf dem iPhone |
| Region | Bayerischer Wald und Böhmerwald, Umkreis 100 km um den gewählten Ort |

Vorbild war die Querformat-Ansicht von [df0zw.github.io/WETTER](https://df0zw.github.io/WETTER/). Anders als dort erzeugt kein Server ein Bild, sondern der Browser holt die Daten selbst und baut die Seite responsiv auf.

## Architektur

Es gibt keinen eigenen Server: GitHub liefert die Seite und die vorab geholten Dateien aus, alles andere fragt der Browser des Besuchers selbst ab.

*(Architekturdiagramm siehe IT-Dokumentation in Claude Docs)*

Oben der Weg über GitHub (Quellen ohne Browser-Schnittstelle, zweimal pro Stunde), unten der direkte Weg vom Browser zu den offenen Schnittstellen (alle 10 Minuten).

## Datenquellen und Schnittstellen

Sechs Anbieter liefern die Daten. Bright Sky, BfS und OpenStreetMap fragt der Browser direkt ab; HND Bayern, DWD-Gesundheitsdaten und NOAA holt ein GitHub-Abholdienst und legt sie als JSON-Datei ins Repository.

| Quelle | Daten | Endpunkt | Abruf | Takt |
| --- | --- | --- | --- | --- |
| [Bright Sky](https://brightsky.dev) (DWD Open Data) | Messwerte inkl. Luftdruckverlauf, MOSMIX-Vorhersage inkl. Sonneneinstrahlung und Taupunkt, Stationsliste, Warnungen | `api.brightsky.dev` `/current_weather`, `/weather`, `/sources`, `/alerts` | Browser | alle 10 min |
| Bright Sky (DWD RADOLAN) | Regenradar, 1 h Messung + 2 h Vorhersage, 5-min-Raster, 1 km | `api.brightsky.dev/radar` | Browser | alle 10 min |
| [BfS ODL-Messnetz](https://odlinfo.bfs.de/ODL/EN/service/data-interface/data-interface_node.html) | Gamma-Ortsdosisleistung DE, Stundenwert und 7-Tage-Verlauf | WFS `www.imis.bfs.de/ogc/opendata/ows`, Ebenen `odlinfo_odl_1h_latest`, `odlinfo_timeseries_odl_1h` | Browser | höchstens stündlich |
| BfS (EURDEP) | Ortsdosisleistung Tschechien | gleicher WFS, Ebene `eurdep_latestValue` | Browser | mit ODL |
| [HND Bayern](https://www.hnd.bayern.de/pegel) | Wasserstand, Abfluss, Meldestufe von 31 Pegeln an Regen und Chamb | HTML-Seite `www.hnd.bayern.de/pegel` | GitHub Actions → `pegel.json` | 2× pro Stunde |
| DWD Open Data (Gesundheit) | UV-Index (Regensburg, Großer Arber), Pollenflug Region Allgäu/Oberbayern/Bay. Wald, Biowetter Zone Niederbayern/Oberpfalz | `opendata.dwd.de/climate_environment/health/alerts/uvi.json`, `s31fg.json`, `biowetter.json` | GitHub Actions → `extra.json` | 2× pro Stunde |
| DWD Open Data (Klima) | Schneehöhe Station Großer Arber (01832, 1436 m), Tageswert vom Vortag | `opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/recent/` | GitHub Actions → `extra.json` | 2× pro Stunde |
| [NOAA SWPC](https://www.swpc.noaa.gov) | Kp-Index-Vorhersage (Polarlicht) | `services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json` | GitHub Actions → `extra.json` | 2× pro Stunde |
| OpenStreetMap | Kartenkacheln für das Radar | `tile.openstreetmap.org` | Browser | bei Bedarf |
| eigene Berechnung | Sonnen- und Mondauf- und -untergang, Mondphase, Strahlung bei wolkenlosem Himmel | keine Quelle, im Browser berechnet | Browser | bei jedem Aufbau |

Eingebundene Bibliotheken: Leaflet 1.9.4 über cdnjs für die Radarkarte, Schriften Big Shoulders Display und Barlow über Google Fonts. Keine Quelle verlangt einen Zugangsschlüssel.

## Repository, Hosting und Deployment

Jede Änderung im Zweig `main` geht ohne Build-Schritt live: GitHub Pages veröffentlicht den Stand nach 1 bis 2 Minuten.

| Datei / Ordner | Inhalt | gepflegt von |
| --- | --- | --- |
| `index.html` | Live-Seite: HTML, CSS und JavaScript in einer Datei | Hand (Claude) |
| `test/index.html` | Testseite für neue Funktionen; seit 27.10.2026 21:10 gleicher Stand wie Live (Pfade mit ../, Kennzeichen „Testseite“) | Hand (Claude) |
| `manifest.webmanifest` | App-Name „Bayerwald“, Farben, Symbole für die Installation | Hand |
| `sw.js` | Service Worker (Cache `bayerwald-v``5`): Seite offline öffnen, Netz zuerst | Hand |
| `icon-192.png`, `icon-512.png`, `apple-touch-icon.png` | App-Symbol (Mond über Bergkämmen) | Hand |
| `scripts/pegel.py` | holt die Pegel von HND Bayern | Hand |
| `scripts/extra.py` | holt UV, Pollen, Kp-Index, Biowetter, Schneehöhe Arber | Hand |
| scripts/archiv.py | baut das Archiv im Zweig daten: DWD-Tageswerte je Ort seit 1991, Bayern-Jahresmittel, Pegelarchiv, Strahlung DE und CZ | Hand |
| `.github/workflows/pegel.yml` | Zeitplan des Abholdienstes | Hand |
| `pegel.json` | Pegelwerte mit 48-h-Verlauf | Abholdienst (`pegel-bot`) |
| `extra.json` | UV, Pollen, Kp-Index, Biowetter, Schneehöhe; Fehler je Quelle unter `errors` | Abholdienst (`pegel-bot`) |
| Zweig daten (eigener Git-Zweig) | Archivdateien, getrennt von main; die Seite liest sie über raw.githubusercontent.com/mknxb/wetter/daten/… | Abholdienst (pegel-bot) |
| `README.md` | Kurzbeschreibung | Hand |

- **Hosting:** GitHub Pages aus Zweig `main`, Ordner `/ (root)`. Keine eigene Domain.
- **Commits:** Änderungen an der Seite laufen unter „Matthias Brem“, Daten-Updates unter „pegel-bot“. Der Bot schreibt etwa 48 Commits am Tag.
- **Testseite:** liest `../pegel.json` und `../extra.json` aus dem Hauptordner, hat kein Manifest, keinen Service Worker und ist für Suchmaschinen gesperrt (`noindex`).

## Automatisierte Datenabholung (GitHub Actions)

Der Workflow „Daten abholen (Pegel, UV, Pollen, Polarlicht)“ läuft zweimal pro Stunde in der GitHub-Cloud und schreibt `pegel.json` und `extra.json` ins Repository.

| Merkmal | Einstellung |
| --- | --- |
| Datei | `.github/workflows/pegel.yml` |
| Zeitplan | `7,37 * * * *` (UTC), also Minute 7 und 37 jeder Stunde; GitHub startet geplante Läufe oft einige Minuten später |
| Weitere Auslöser | manuell (`workflow_dispatch`), bei Änderungen unter `scripts/` oder am Workflow |
| Umgebung | `ubuntu-latest`, Python 3.12, nur Standardbibliothek, Zeitlimit 5 min |
| Rechte | `contents: write` (nur für das eigene Repository) |
| Parallelität | `concurrency: pegel`, nie zwei Läufe gleichzeitig |

Ablauf eines Laufs:

1. Repository auschecken, Python einrichten.
2. `scripts/pegel.py`: lädt `www.hnd.bayern.de/pegel`, liest an den Pegelsymbolen die Attribute `data-wert` (Wasserstand cm), `data-wert2` (Abfluss m³/s), `data-ms` (Meldestufe), `data-datum`, `data-stoerung`. Berücksichtigt werden alle Pegelnummern mit Präfix `152` (Einzugsgebiet Regen und Chamb). Pro Pegel bleibt ein Verlauf von 48 h für die Tendenz. Findet es keinen Pegel, bricht der Lauf mit Fehler ab.
3. `scripts/extra.py`: holt UV-Index, Pollenflug, Kp-Index, Biowetter und die Schneehöhe am Großen Arber (Station über das DWD-Verzeichnis der aktuellen Tageswerte gefunden). Jede Quelle ist unabhängig; fällt eine aus, bleibt deren letzter Stand erhalten und die Fehlermeldung steht in `extra.json` unter `errors`. Der Schritt darf scheitern, ohne den Lauf abzubrechen.
4. Sind die Daten neu, committet `pegel-bot` beide Dateien („Daten TT.MM. HH:MM“) und pusht nach `main`.

Die Seite zeigt den Stand der Pegeldaten an und weist darauf hin, wenn er älter als 2 Stunden ist.

## Archiv (Zweig daten)

Seit 27.10.2026 schreibt `scripts/archiv.py` bei jedem Lauf ein eigenes Archiv in den Git-Zweig `daten`; die Seite liest es direkt von GitHub. Jeder Teil läuft unabhängig, Fehler stehen in `status.json`.

| Datei | Inhalt | Quelle und Takt |
| --- | --- | --- |
| tage/<ort>.csv | Tageswerte seit 1991: Tmin, Tmax, Mittel, Regen, Sonne, Schnee, Böe, Wind, Feuchte | DWD-Klimastation (KL) mit aktuellen Daten innerhalb 60 km; Regen und Schnee von der nächsten Niederschlagsstation (RR) innerhalb 15 km; täglich |
| stationen.json | welche DWD-Stationen zu welchem Ort gehören | täglich |
| bayern-jahre.csv | Jahresmitteltemperatur Bayern seit 1881 (Wärmestreifen) | DWD-Gebietsmittel; täglich |
| pegel/JJJJ-MM.csv, pegel-tage.csv | eigene Mitschrift aller Pegel (Einzelwerte, Tagesmittel, -min, -max) | aus pegel.json; alle 30 min, seit 26.10.2026 |
| pegel-meldestufen.json | Mittelwasser und Meldestufen der Hauptpegel | HND-Detailseiten; täglich |
| odl-aktuell.json | je Ort bis zu 6 BfS-Sonden im Umkreis von 60 km mit 7-Tage-Stundenverlauf und Wochenmittel, dazu unter cz die 4 nächsten tschechischen Sonden | BfS WFS und EURDEP; alle 30 min |
| odl/<kennung>.csv | Tagesmittel je Sonde (DE: vom BfS, Jahre zurück; CZ: aus eigener Mitschrift) | täglich bzw. alle 30 min |
| odl-cz/<id>.csv | eigene Mitschrift der tschechischen Stundenwerte (EURDEP liefert nur den letzten Wert) | alle 30 min, seit 27.10.2026 |

Klimanormale 1991–2020 (pro Kalendertag, ±7 Tage geglättet) und alle Rückblick-Werte rechnet die Seite selbst aus `tage/<ort>.csv`.

## Funktionen und Berechnungslogik

Die Seite lädt alle Bereiche parallel, zeichnet sie alle 10 Minuten neu und beim Zurückkehren in den Tab, wenn der letzte Abruf älter ist. Fällt eine Quelle aus, zeigt nur ihr Bereich einen Hinweis.

| Bereich | Inhalt | Logik und Schwellen |
| --- | --- | --- |
| Kopf (Hero) | Ort, aktuelle Messung, Tendenz, Klima-Hinweis (Abweichung vom Normal 1991–2020), Wind mit Böen, Regen heute, Feuchte, Luftdruck mit Tendenz, Sonne, Mond, Himmel und Bergsilhouette | Start in Blaibach oder im per Stern gemerkten Ort; 10 Orte wählbar, alternativ `?ort=` oder `?lat=&lon=&name=`. Messung von der nächsten Station. Temperaturtendenz: Vergleich mit dem Wert vor rund 3 h, ab ±0,7 °C. Luftdrucktendenz über 3 h: gleichbleibend unter 0,5 hPa, leicht bis 1,5, normal bis 3,5, stark darüber. Sonnen- und Mondzeiten, Mondphase und Beleuchtung berechnet. Himmelsfarbe nach Wettersymbol und Tageszeit. Silhouette: weiche Mittelgebirgsrücken, Fichtenwald, Talnebel, Großer Arber mit Kleinem Arber und zwei Radarkuppeln. |
| Heute im Bayerwald | 12 Kacheln, immer für den oben gewählten Ort (neu: Waldbrandindex nach eigener FWI-Berechnung, November bis Februar ausgeblendet), zutreffende zuerst (orange), „vielleicht“ blau, sonst grau; die 6 wichtigsten sichtbar, „Alle anzeigen“ für den Rest; Tipp öffnet Erklärung | siehe Tabelle unten |
| Nächste 36 Stunden | Temperaturkurve, Regenbalken, 0-°C-Linie, 3-Stunden-Kacheln | MOSMIX-Stundenwerte. Mit Finger oder Maus nachfahren: Linie, Punkt und Kästchen mit Uhrzeit, Temperatur, Regen, Wind; bleibt nach dem Loslassen 3 s stehen. |
| Regenradar | Film über 3 h im 5-min-Takt auf OpenStreetMap-Karte, Kurzantwort „Regen ab …“ | RADOLAN-Gitter (polarstereografisch) wird im Browser auf Web-Mercator umgerechnet, 75 km um den Ort. Farbstufen 0,1 bis 40 mm/h. Regen am Ort = mindestens 0,1 mm/h im Umkreis von 2 km. |
| Die nächsten Tage | 4 Tage mit Tief, Hoch, Temperaturbalken, Regen, Böen | Regensymbol ab 0,5 mm am Tag (0,1 mm je 3 h), Schnee bei Höchstwert unter 1 °C. Böen nur aus eigenen Werten, nicht von Nachbarstationen. |
| Warnungen | DWD-Warnungen | zuerst für den gewählten Ort, darunter „In der Umgebung“ für die 5 nächsten Orte |
| Gewässer | zwei Pegel je Ort (Blaibach: Kötzting und Chamerau), Regenmengen 24 h und 3 Tage, alle Pegel der Region aufklappbar. Pegel antippen → Verlauf 7 Tage, 30 Tage, 1 Jahr mit Mittelwasser und Meldestufe 1. Talsperre Frauenau als Füllstand in % (Näherung, 100 % = Stauziel 767 m), Drachensee als cm zum Dauerstau 405,00 m und belegter Rückhalteraum | Hinweis bei Meldestufe 1 bis 4. Frühwarnung bei Anstieg um 15 cm oder mehr in rund 3 h am Oberlauf (Weißer, Schwarzer, Großer, Kleiner Regen, Teisnach, Aitnach). |
| Kälteste Orte | Jetzt und Tiefstwert 12 h, je Top 10/8 | Stationen im Umkreis 100 km, Meldung jünger als 6 h, nur echte Messwerte (keine Vorhersage, keine Ersatzwerte). |
| Strahlung | Status (normal, nach Regen, erhöht), bis zu 6 BfS-Sonden (60 km) mit Abweichung vom Wochenmittel und 24-h-Änderung, 4 tschechische Sonden. Sonde antippen → Verlauf 7 Tage (Stundenwerte), 30 Tage, 1 Jahr (Tagesmittel) und Einordnungsskala | Werte in µSv/h aus dem Archiv (EURDEP-nSv/h umgerechnet). Natürlich 0,05–0,2; nach Regen bis etwa 3-fach. Erhöht: mehr als 3-fach ohne Regen oder über 24 h an mehreren Sonden. Logarithmische Skala: 1 mSv/Jahr ≈ 0,11 µSv/h zusätzlich; Aufenthalt in Gebäuden ab ≈ 60, Evakuierung ab ≈ 600 µSv/h (NDWV, 7 Tage). |
| Rückblick | Temperatur: 30 Tage (Tief/Hoch über dem Normalband) oder 12 Monate (Abweichung), Rekorde, Wärmestreifen Bayern seit 1881. Regen: Tage, Wochen, Monate (mit Normal), Jahr kumuliert gegen Vorjahr und Normal, Hinweis auf Trockenphasen | Aus dem Archiv tage/<ort>.csv; heute aus Messung und Vorhersage. Diagramme zum Nachfahren mit Finger oder Maus. Strahlung und Gewässer stehen als Verlauf direkt in ihren Karten. |
| App | Installierbar als „Bayerwald“, startet im Vollbild | Manifest + Service Worker; HTML aus dem Netz, bei Funkloch aus dem Zwischenspeicher; Live-Daten nie zwischengespeichert. |

Regeln der Kacheln „Heute im Bayerwald“:

| Kachel | Quelle | leuchtet (orange) | „vielleicht“ (blau) |
| --- | --- | --- | --- |
| Inversion | Station Großer Arber vs. nächste Talstation unter 550 m | Arber wärmer als das Tal | oben mehr als 3 K wärmer als der normale Abfall von 0,65 K je 100 m |
| Alpenblick | Sichtweite und Feuchte am Arber | Sicht ab 60 km und Feuchte unter 75 %, tagsüber | Sicht ab 35 km, oder klare Luft nachts |
| Radl-Fenster | MOSMIX-Stundenwerte | mind. 2 h am Stück heute: trocken, Regenrisiko unter 30 %, Böen unter 40 km/h, ab 4 °C, bei Tageslicht | gleiches Fenster erst morgen |
| Morgenfrost | MOSMIX 4 bis 9 Uhr, vor 8 Uhr für heute, sonst für morgen | Tiefstwert bis 0 °C („Scheibe kratzen“) oder bis 1 °C mit Niederschlag („Glätte“) | bis 3 °C (Reif oder Bodenfrost möglich) |
| PV morgen | MOSMIX-Sonneneinstrahlung, verglichen mit berechnetem wolkenlosem Tag | ab 70 % des wolkenlosen Tages | ab 45 %; zusätzlich stärkste drei Stunden |
| Sternenhimmel | MOSMIX-Bewölkung 20 bis 4 Uhr, Mondphase und Mondstand um Mitternacht, Sternschnuppen-Termine | Bewölkung unter 30 % und Mond nicht hell | klar mit hellem Mond, oder Bewölkung unter 60 % |
| UV-Index | DWD, Raum Regensburg (+ Arber) | ab 6 | ab 3 |
| Pollen | DWD, Allgäu/Oberbayern/Bay. Wald | stärkste Art mittel oder höher | gering bis mittel |
| Biowetter | DWD-Biowetter, Zone Niederbayern/Oberpfalz | ein Einfluss „hoch“ | ein Einfluss „gering“ |
| Polarlicht | NOAA Kp-Index, nächste 24 h, Bewölkung nachts | Kp ab 7 | Kp ab 6, oder Kp ab 7 bei starker Bewölkung |
| Schnee Arber | DWD-Schneehöhe Großer Arber (Vortag), MOSMIX-Niederschlag bei Frost für 48 h | ab 5 cm Neuschnee oder ab 20 cm Schnee | etwas Schnee oder Neuschnee; Mai bis Oktober ohne Schnee ausgeblendet |

Inversion, Alpenblick, Sternenhimmel und PV morgen sind Faustregeln aus Mess- und Vorhersagewerten, keine amtlichen Produkte. Das Biowetter ist ein DWD-Produkt und kein ärztlicher Rat.

## Sicherheit und Datenschutz

Die Live-Seite verarbeitet keine personenbezogenen Daten selbst und hält keine Geheimnisse im Repository; Risiken liegen bei den Drittanbietern, die der Browser direkt anspricht.

**Geheimnisse und Rechte**

- Im Repository liegen keine Passwörter, Token oder Schlüssel. Keine der Datenquellen braucht einen.
- Der Abholdienst nutzt nur das automatische GitHub-Token mit Schreibrecht auf dieses eine Repository.
- Live- und Testseite nutzen keine Cookies; im Browserspeicher (localStorage) liegt nur der per Stern gewählte Startort, er verlässt das Gerät nicht. Die frühere Home-Assistant-Anbindung der Testseite wurde am 27.10.2026 entfernt.

**Datenübermittlung an Dritte**

Beim Aufruf übermittelt der Browser die IP-Adresse des Besuchers an: Bright Sky, BfS, OpenStreetMap-Kachelserver, cdnjs (Cloudflare) und Google Fonts. Die Seite ist öffentlich erreichbar.

**Lizenzen und Quellenangaben**

- DWD-Daten: Quellenvermerk „Deutscher Wetterdienst“ steht im Fuß der Seite.
- OpenStreetMap: Namensnennung in der Radarkarte.
- BfS und EURDEP: Nutzungsbedingungen des BfS-Geoportals.
- HND Bayern: Quelle am Pegelbereich genannt. Es gibt keine offizielle Schnittstelle; die Werte werden aus der öffentlichen Pegelübersicht gelesen. Die Nutzungsbedingungen des Landesamts für Umwelt sind nicht geprüft.
- NOAA: gemeinfreie Daten der US-Regierung.

**Technische Schutzmaßnahmen**

- Alle Texte aus externen Quellen werden vor der Anzeige maskiert (Schutz vor eingeschleustem HTML).
- Die Seite läuft nur über HTTPS (GitHub Pages).

**Empfehlungen**

- [ ] Google Fonts lokal im Repository ablegen, damit keine IP-Adressen an Google gehen.
- [ ] Leaflet mit Integritätsprüfung (SRI-Hash) einbinden oder lokal ablegen.
- [ ] Nutzungsbedingungen von HND Bayern / LfU für das automatische Auslesen klären.
- [ ] Falls in Home Assistant ein Token „Wetterseite“ angelegt wurde: dort löschen.

## Betrieb, Wartung und Fehlerbehebung

Im Normalbetrieb ist nichts zu tun: Die Seite holt ihre Daten selbst, der Abholdienst läuft automatisch.

**Änderungsprozess**

1. Neue Funktion oder Korrektur zuerst in `test/index.html` einbauen und unter `/wetter/test/` prüfen.
2. Nach Freigabe („auf Live übernehmen“) in `index.html` übernehmen; Pfade auf `pegel.json` und `extra.json` wieder ohne `../`.
3. Nach dem Push 1 bis 2 Minuten warten, Seite neu laden und prüfen.

**Abholdienst von Hand starten:** GitHub → Repository `wetter` → Reiter „Actions“ → „Daten abholen …“ → „Run workflow“.

| Fehlerbild | wahrscheinliche Ursache | Maßnahme |
| --- | --- | --- |
| Ein Bereich zeigt „Daten gerade nicht abrufbar“ | Quelle kurz nicht erreichbar | 10 min warten; hält es an, Status der Quelle prüfen |
| Pegel mit Hinweis „älter als 2 Stunden“ | Abholdienst gescheitert oder pausiert | Reiter „Actions“: letzten Lauf öffnen; „Keine Pegel gefunden“ = HND hat den Seitenaufbau geändert → `scripts/pegel.py` anpassen |
| UV, Pollen oder Polarlicht bleiben alt | eine Quelle in `extra.py` liefert Fehler | Protokoll des Schritts `extra.py` im letzten Lauf lesen |
| Änderung nicht sichtbar | GitHub Pages noch nicht fertig oder alte Version im Browser | 2 min warten, neu laden; installierte App einmal ganz schließen und neu öffnen |
| Radarkarte grau oder ohne Orte | OpenStreetMap-Kacheln oder Leaflet (cdnjs) nicht erreichbar | später erneut; bei Dauerproblem Leaflet lokal ablegen |
| Kachel „Inversion“ oder „Alpenblick“ ohne Daten | Station Großer Arber meldet nicht | keine Maßnahme nötig, kommt mit der nächsten Meldung zurück |
| Strahlung leer | BfS-Server nicht erreichbar oder blockt Browserabfragen | prüfen, ob der Fehler dauerhaft ist; dann Abruf in den Abholdienst verlagern |

## Bekannte Einschränkungen und offene Punkte

Das größte Betriebsrisiko ist das Auslesen der HND-Seite ohne offizielle Schnittstelle; zwei Bereiche (Strahlung, Radar-Lage) sind mit echten Daten noch nicht bestätigt.

| Thema | Einschränkung oder Risiko | Folge | Maßnahme |
| --- | --- | --- | --- |
| Pegel HND Bayern | kein offizieller Dienst, Auslesen der HTML-Seite | Ändert Bayern die Seite, bleiben die Pegel stehen | Hinweis „älter als 2 Stunden“ beachten, Skript anpassen |
| Strahlung | Werte kommen über den Abholdienst; Abruf aus dem Browser beim BfS nur als Rückfall. Tschechische Verläufe gibt es erst ab 27.10.2026 (eigene Mitschrift) | CZ-Diagramme anfangs kurz; fällt der Abholdienst aus, veralten die Werte | füllt sich von selbst; Stand in status.json prüfen |
| Regenradar | Umrechnung des Radargitters auf die Karte selbst gebaut | Regengebiete könnten leicht versetzt liegen | an einem Regentag mit einer anderen Radar-App vergleichen |
| Tschechische Wetterstationen | nur große Stationen über SYNOP (z. B. Churáňov, Přimda); CHMI hat keine Browser-Schnittstelle | kleinere Orte wie Horská Kvilda fehlen | bei Bedarf CHMI über den Abholdienst holen |
| Schnee Arber | Tageswert der DWD-Station erscheint mit einem Tag Versatz | Schneehöhe zeigt den Stand von gestern | in der Kachel steht das Messdatum |
| Waldbrand- und Graslandfeuer-Index | keine offene amtliche Quelle; die Kachel rechnet den FWI selbst aus Temperatur, Feuchte, Wind und Regen | Abweichungen zum DWD-Index möglich | bei echter Gefahr den amtlichen Index auf dwd.de prüfen; im Frühjahr mit DWD-Werten abgleichen |
| GitHub-Zeitplan | geplante Läufe starten oft verspätet; in öffentlichen Repositories pausiert GitHub Zeitpläne nach 60 Tagen ohne Aktivität | Daten lückenhaft oder Abholdienst steht | Lauf im Reiter „Actions“ gelegentlich prüfen und ggf. wieder aktivieren |
| Commit-Historie | rund 48 Bot-Commits pro Tag | lange, unübersichtliche Historie | Archiv liegt bereits im Zweig daten; pegel.json und extra.json bleiben auf main |
| Datenquellen ohne Zusage | Bright Sky ist ein kostenloser Community-Dienst ohne Verfügbarkeitszusage | Ausfall legt Wetter, Radar und Warnungen lahm | hinnehmen; Ausweichquelle wäre die DWD-Open-Data-Ablage |
| Pegelarchiv | eigene Mitschrift erst seit 26.10.2026; HND bietet keine offene Langzeitreihe | Pegelverläufe anfangs kurz | füllt sich von selbst |
| Füllstand Talsperre Frauenau | keine amtliche Inhaltslinie veröffentlicht; Näherung V ~ ((h − 700) / 67)^3,46, abgeglichen an einen Wert von alarmaa.de (753,30 m ≈ 8,96 Mio m³) | Prozentwert kann einige Punkte daneben liegen; Tendenz stimmt | Anzeige mit „ca.“; bei Gelegenheit Inhaltslinie beim WWA Deggendorf erfragen |
| Faustregeln | Inversion, Alpenblick, Sternenhimmel und PV morgen sind Schätzungen | Fehlalarme möglich | an echten Tagen nachschärfen |

## Änderungshistorie

Die Live-Seite entstand am 26.10.2026; seitdem kamen Radar, Strahlung, Pegel, 11 Signal-Kacheln, Mond und die App-Installation hinzu. Quelle: Commit-Historie im Repository (ohne die automatischen Daten-Commits).

| Datum | Seite | Änderung |
| --- | --- | --- |
| 28.10.2026 21:45 | Daten | Archiv: wieder bis zu 6 Strahlungssonden je Ort; Zwischenstand nach jedem Teil, Laufzeit je Teil in status.json. Tschechische Werte fehlen seit 27.10.: BfS meldet „Feature type opendata:eurdep_latestValue unknown“; mehrere Abfragevarianten eingebaut, Abwarten vereinbart |
| 28.10.2026 21:08 | Live | Startort per Stern neben dem Ortsnamen (localStorage-Schlüssel wetter-startort, nur auf dem Gerät; Standard Blaibach; ?ort= hat Vorrang); neue Orte Walderbach (Pegel Kienhof, Nittenau) und Bruck i.d.OPf. (Nittenau, Marienthal), auch im Archiv; Cache bayerwald-v5 |
| 27.10.2026 21:32 | Live | Ziehende Wolken nach Bewölkungsgrad und Wind; Sterne nach Bewölkung abgestuft; Mondlicht hellt den Nachthimmel auf und dämpft Sterne; Bewölkung aus der DWD-Vorhersage für den Ort, wenn die Wolkenstation mehr als 15 km entfernt ist (z. B. Weiding misst keine Wolken); Cache bayerwald-v4 |
| 27.10.2026 21:10 | Live | Step 2 von der Testseite übernommen: Archiv, Rückblick (Temperatur, Regen), Regenmengen, Klima-Hinweis, Waldbrandindex, Warnungen je Ort, Strahlung mit Status, Verlauf und Einordnung je Sonde, Pegelverläufe zum Aufklappen, Füllstand der Speicher, vollständige Quellen; Service-Worker-Cache auf bayerwald-v3 |
| 27.10.2026 20:41 | Daten | tschechische Strahlungswerte (EURDEP) werden selbst mitgeschrieben |
| 27.10.2026 ab ca. 15:00 | Test | Step 2 schrittweise aufgebaut und mit Matthias abgestimmt (Strahlungsskala, Verläufe in den Karten, Rückblick hinter Strahlung) |
| 27.10.2026 ca. 16:00 | Daten | Archiv im Zweig daten eingerichtet (scripts/archiv.py): DWD-Tageswerte seit 1991, Bayern seit 1881, Pegel, Strahlung |
| 27.10.2026 14:44 | Live | Testseite übernommen: Mond, 5 neue Kacheln, Luftdrucktendenz, Kurve zum Nachfahren, neue Bergsilhouette; Service-Worker-Cache auf `bayerwald-v2` |
| 27.10.2026 14:08 | Test | Home-Assistant-Karte entfernt, gespeicherter Zugang wird im Browser gelöscht |
| 27.10.2026 13:37 | Test | Großer Arber nach echtem Profil mit Kleinem Arber und zwei Radarkuppeln |
| 27.10.2026 13:33 | Live + Test | Fehler behoben: Sonnenzeiten ab 13 Uhr für den Folgetag berechnet (Nachthimmel am Nachmittag) |
| 27.10.2026 13:31 | Test | neue Bergsilhouette mit Fichtenwald und Talnebel |
| 27.10.2026 12:54 | Test | Luftdrucktendenz und Temperaturkurve zum Nachfahren |
| 27.10.2026 12:36 | Test | Mond, Sternenhimmel, PV morgen, Morgenfrost, Biowetter, Schnee Arber |
| 27.10.2026 12:32 | Daten | Abholdienst für Biowetter und Schneehöhe Großer Arber; Fehler je Quelle in `extra.json` |
| 27.10.2026 07:39 | Test | Karte „Zuhause“ mit Home Assistant (Energiefluss live) |
| 27.10.2026 07:35 | Test | Testseite unter `/test/` angelegt |
| 26.10.2026 22:32 | Live | Radl-Fenster nur bei Tageslicht; Stationsnamen ohne Kreiszusatz |
| 26.10.2026 22:27 | Live | „Heute im Bayerwald“ mit 6 Signalen; als App installierbar |
| 26.10.2026 22:25 | Daten | Pollen für Teilregion Bayerischer Wald; UV auch für den Arber |
| 26.10.2026 22:24 | Daten | Abholdienst für UV-Index, Pollenflug und Kp-Index |
| 26.10.2026 22:18 | Live | Bereich „Gewässer“ mit Meldestufen und Frühwarnung |
| 26.10.2026 22:17 | Daten | Pegel-Abholdienst für HND Bayern eingerichtet |
| 26.10.2026 21:35 | Live | tschechische Strahlungssonden (EURDEP) |
| 26.10.2026 21:29 | Live | Radarkarte auf OpenStreetMap umgestellt; Böen ohne Nachbarstationen |
| 26.10.2026 21:24 | Live | Regenradar und Strahlung (BfS) |
| 26.10.2026 21:13 | Live | neues Design, Start immer in Blaibach |
| 26.10.2026 20:49 | Live | Ortsnamen, nur echte Messwerte bei Tiefstwerten, Regensymbol nach Menge |
| 26.10.2026 ca. 20:30 | Live | erste Version von Hand hochgeladen, Repository angelegt |

