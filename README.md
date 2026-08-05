# Hospitaal Binnenshuise Navigasie

Hierdie projek is 'n binnenshuise navigasiestelsel vir 'n hospitaal. Dit gebruik 'n topologiese grafiek en die A*-algoritme om die vinnigste toegelate roete tussen twee plekke te bereken. Die stelsel neem vloere, hysbakwagtyd, trappe, gebouverbindings en gebruikerstoegang in ag.

## Hooffunksies

- Soek bestemmings volgens naam, node-ID, nodetipe, gebou of vloer.
- Bereken die vinnigste roete tussen twee nodes.
- Beperk roetes volgens die gebruiker se toegangsregte.
- Wys die roete, node-telling en beraamde reistyd as JSON.
- Genereer 'n PNG-vloerplan waarop die roete uitgelig is.
- Wys 'n interaktiewe webkoppelvlak met vloer-oortjies en roetestappe.

Die ondersteunde gebruikerstipes is:

| Gebruikerstipe | Toegang |
|---|---|
| `PUBLIEK` | Openbare areas |
| `PERSONEEL` | Openbare, personeel- en ICU-areas |
| `PASIENT_VERVOER` | Openbare en personeelareas |
| `NOODGEVAL` | Alle gedefinieerde areas |

## Tegnologie

- Python 3.10 of nuwer
- FastAPI en Uvicorn
- SQLite
- Matplotlib
- HTML, CSS, JavaScript en SVG
- Pytest

## Projekstruktuur

| Lêer | Doel |
|---|---|
| `main.py` | FastAPI-toepassing en HTTP-eindpunte |
| `HospitaalGrafiek.py` | Databasislaaier, bestemmingsoektog en A*-roetebepaling |
| `VloerPlan.py` | Matplotlib-vloerplan en roeteprent |
| `Skema.sql` | SQLite-databasisskema |
| `SeedData.sql` | Voorbeeldgeboue, vloere, nodes en rande |
| `hospitaal_wayfinder.html` | Interaktiewe webkoppelvlak |
| `test_main.py` | Geoutomatiseerde API-toetse |
| `.gitignore` | Verhoed dat gegenereerde lêers na Git gestoot word |

## Installasie

Clone die repository en beweeg na die projekgids:

```powershell
git clone ssh://git@gitlab.akademia.ac.za:2222/ngpro262/hospitaalnav.git
cd hospitaalnav
```

Skep en aktiveer 'n virtuele omgewing:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Installeer die afhanklikhede:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Begin die API

Begin FastAPI vanuit die projekgids:

```powershell
python -m uvicorn main:app --reload
```

Die volgende adresse is dan beskikbaar:

- API: `http://127.0.0.1:8000`
- Swagger-dokumentasie: `http://127.0.0.1:8000/docs`
- OpenAPI-skema: `http://127.0.0.1:8000/openapi.json`

Die databasis word standaard uit `Skema.sql` en `SeedData.sql` herbou wanneer die API begin. Stel die volgende omgewingsveranderlike om dit af te skakel:

```powershell
$env:AUTO_HERBOU_DB="false"
python -m uvicorn main:app --reload
```

## Begin die webkoppelvlak

Hou die API aan die gang en open 'n tweede PowerShell-venster in die projekgids:

```powershell
python -m http.server 5500
```

Open daarna:

```text
http://127.0.0.1:5500/hospitaal_wayfinder.html
```

Die API-basis-URL in die webkoppelvlak moet `http://localhost:8000` wees. Gebruik die soekvelde om die beskikbare beginpunte en bestemmings te filtreer, kies 'n opsie uit elke keuselys en klik **Vind Roete**.

## API-eindpunte

### `GET /`

Gee 'n verwelkomingsboodskap terug.

### `GET /destinations`

Soek mensleesbare bestemmings.

| Parameter | Vereis | Beskrywing |
|---|---:|---|
| `q` | Nee | Naam, node-ID, tipe, gebou of vloer |
| `limiet` | Nee | Maksimum resultate, tussen 1 en 100; verstek is 20 |

Voorbeeld:

```text
GET http://127.0.0.1:8000/destinations?q=Radiologie
```

### `GET /route`

Bereken 'n toegelate roete.

| Parameter | Vereis | Beskrywing |
|---|---:|---|
| `begin` | Ja | Beginnode se ID |
| `doel` | Ja | Eindnode se ID |
| `gebruiker_tipe` | Nee | Verstek is `PUBLIEK` |

Voorbeeld:

```text
GET http://127.0.0.1:8000/route?begin=MAIN-G-ENT&doel=ANNEX-1-RAD&gebruiker_tipe=PUBLIEK
```

Voorbeeldantwoord:

```json
{
  "begin_node": "MAIN-G-ENT",
  "doel_node": "ANNEX-1-RAD",
  "gebruiker_tipe": "PUBLIEK",
  "geskatte_tyd_sekondes": 83.0,
  "node_telling": 9,
  "pad": [
    "MAIN-G-ENT",
    "MAIN-G-J01",
    "MAIN-G-STA",
    "MAIN-1-STA",
    "MAIN-1-J01",
    "MAIN-1-BRIDGE",
    "ANNEX-1-BRIDGE",
    "ANNEX-1-ELV",
    "ANNEX-1-RAD"
  ]
}
```

### `GET /route/image`

Bereken die roete en lewer 'n PNG-vloerplan waarop dit uitgelig is.

```text
GET http://127.0.0.1:8000/route/image?begin=MAIN-G-ENT&doel=ANNEX-1-RAD&gebruiker_tipe=PUBLIEK
```

## Algemene HTTP-antwoorde

| Status | Betekenis |
|---:|---|
| `200` | Versoek was suksesvol |
| `400` | Begin- of eindnode bestaan nie |
| `403` | Geen toegelate roete bestaan vir die gebruikerstipe nie |
| `422` | Vereiste parameters ontbreek of is ongeldig |

## Toetse

Voer die toetsstel uit met:

```powershell
python -m pytest -q
```

Die huidige toetse bevestig dat:

- Radiologie volgens naam gevind word.
- Soektogte nie hooflettersensitief is nie.
- Nooddienste as `MAIN-G-ER` beskikbaar is.
- 'n gevonde bestemming in 'n roeteversoek gebruik kan word.

## Databasismodel

Die hospitaal word as 'n grafiek gestoor:

- `geboue`: hospitaalgeboue.
- `vloere`: vloere wat aan geboue behoort.
- `node_tipes`: ingange, departemente, gange, hysbakke en ander tipes.
- `nodes`: keusepunte en bestemmings met vloerplankoördinate.
- `rande`: geweegde verbindings tussen nodes.
- `gebruiker_tipes`: ondersteunde gebruikersrolle.
- `toegang_toestemmings`: beperkte groepe wat elke rol mag betree.

'n Rand se roetekoste is die basisreistyd plus enige wagtyd. Die A*-heuristiek gebruik die afstand tussen koördinate en 'n vaste strafwaarde vir vloerveranderings.
