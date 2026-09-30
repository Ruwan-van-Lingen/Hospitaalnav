# Hospitaal Binnenshuise Navigasie

'n Akademiese demonstrasie van binnenshuise hospitaalnavigasie met Python,
FastAPI, SQLite en 'n webkoppelvlak. Die hospitaal word as 'n geweegde grafiek
voorgestel: nodusse is bestemmings of keusepunte en rande is verbindings met
reistye, afstande en toegangsbeperkings.

## Funksies

- Soek bestemmings volgens naam, nodus-ID, nodustipe, gebou of vloer met 'n
  2-4-boom in geheue.
- Bereken toegelate roetes met A*, met wagtyd by die basisreistyd ingesluit.
- Vind die naaste bereikbare nooduitgang met multibron-Dijkstra; hysbakke word
  by ontruiming uitgesluit.
- Wys roetes en sluitings op 'n interaktiewe SVG-kaart of laai 'n PNG-kaart af.
- Bestuur een aktiewe insident deur die beskermde administrasieblad.
- Kontroleer ontruimingsdekking per nodus met parallelle werkprosesse.
- Bereken 'n minimum spanboom of spanwoud met Kruskal.
- Bereken gemodelleerde maksimum vloei na nooduitgange met Edmonds–Karp.

Die voorbeelddata en randkapasiteite is vir demonstrasie. 'n Berekende
ontruimingsroete of vloeisyfer is nie 'n gevalideerde hospitaalveiligheidsplan
of 'n gemete ontruimingsvermoë nie.

## Projekstruktuur

| Lêer | Doel |
|---|---|
| `main.py` | FastAPI-eindpunte, sessies, insidente en werkprosesbestuur |
| `HospitaalGrafiek.py` | Grafieklaai, lambda-formules, A*, Dijkstra, spanboom en maksimum vloei |
| `Boom24.py` | 2-4-boom en geordende bestemmingsoektog |
| `Sorteer.py` | Stabiele invoegsortering en hibriede saamsmeltsortering |
| `mst_en_vloei.py` | Selfstandige leervoorbeelde; die API gebruik `HospitaalGrafiek.py` |
| `VloerPlan.py` | PNG-vloerplan met Matplotlib se nie-interaktiewe `Agg`-agterkant |
| `Skema.sql`, `SeedData.sql` | Databasisstruktuur en demonstrasiedata |
| `hospitaal_wayfinder.html`, `hospitaal_wayfinder.css`, `hospitaal_wayfinder.js` | Openbare navigasiekoppelvlak |
| `admin.html`, `admin.css`, `admin.js` | Administrasiekoppelvlak |
| `test_*.py`, `conftest.py` | Toetse met afsonderlike tydelike databasisse |
| `Dockerfile`, `docker-compose.yml` | Houerbou en blywende databerging |

## Installasie en opstart

Die projek gebruik Python 3.10 of nuwer; die Docker-beeld gebruik Python 3.12.
Git-toegang tot die Akademia-bediener en 'n geregistreerde SSH-sleutel is
nodig om die bewaarplek te kloon.

```powershell
git clone ssh://git@gitlab.akademia.ac.za:2222/rkw/ngpro262/2026/heuningbye.git
cd heuningbye
```

### Plaaslike Python-omgewing

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Stel die omgewing en begin die toepassing:

```powershell
$env:ADMIN_GEBRUIKERSNAAM = "admin"
$env:ADMIN_WAGWOORD = "heuningbye123!"
$env:SESSIE_GEHEIM = "kies-'n-lang-willekeurige-geheim"
$env:AUTO_HERBOU_DB = "false"
python -m uvicorn main:app --reload
```

| Adres | Doel |
|---|---|
| `http://127.0.0.1:8000/ui` | Navigasiekoppelvlak |
| `http://127.0.0.1:8000/admin` | Sluitingsadministrasie |
| `http://127.0.0.1:8000/docs` | Interaktiewe API-dokumentasie |
| `http://127.0.0.1:8000/openapi.json` | OpenAPI-skema |

Die HTML-, CSS- en JavaScript-lêers word deur dieselfde toepassing bedien;
'n tweede webbediener is nie nodig nie.

### Docker

Maak Docker Desktop oop en wag tot die Linux-houerenjin gereed is. Stel
dieselfde administrasieveranderlikes as hier bo en voer uit:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f hospitaalnav
```

Compose stoor SQLite in die benoemde volume `hospitaaldata` by
`/app/data/hospitaal.db`. Die volume bly behoue wanneer die houer herbegin
of herskep word. Die bronkode en afhanklikhede word in die beeld ingesluit;
plaaslike databasisse, geheime, Git-metadata en kaslêers word uitgesluit.

Stop die diens met `docker compose down`. Hierdie opdrag behou die volume.
`docker compose down -v` verwyder ook die volume en dus die databasis;
gebruik dit slegs wanneer jy die data doelbewus wil verwyder.

## Instellings en databerging

| Omgewingsveranderlike | Betekenis |
|---|---|
| `DB_PAD` | Databasispad; verstek is `hospitaal.db` langs `main.py`. Relatiewe paaie word vanaf die projekgids bereken. |
| `AUTO_HERBOU_DB` | `true` herskep die databasis by opstart; `false` behou bestaande data. Plaaslike verstek is `true`; Compose stel `false`. |
| `ADMIN_GEBRUIKERSNAAM` | Administrateur se gebruikersnaam; ontwikkelingsverstek is `admin`. |
| `ADMIN_WAGWOORD` | Administrateur se wagwoord; ontwikkelingsverstek is `heuningbye123!`. |
| `SESSIE_GEHEIM` | Geheim waarmee die administrasiesessie onderteken word. |

'n Ontbrekende databasis word uit die SQL-lêers geskep, ongeag
`AUTO_HERBOU_DB`. Met `true` gaan bestaande insidente en ander
databasisveranderinge by opstart verlore. Gebruik `false` om dit te behou.
Veranderinge aan `SeedData.sql` verander nie outomaties etikette in 'n
bestaande databasis nie.

Vervang die ontwikkelingsbewyse en sessiegeheim vir enige gedeelde ontplooiing.
'n Werklike ontplooiing vereis ook gepaste HTTPS- en toegangsbeheeropstelling.

## Roetes, afstand en gewigte

Die projek gebruik twee benoemde lambda-funksies in die werklike berekeninge:

```python
BEREKEN_AFSTAND = lambda pos_a, pos_b: math.hypot(
    pos_a[0] - pos_b[0], pos_a[1] - pos_b[1]
)
BEREKEN_GEWIG = lambda basis_gewig_s, wag_penalty_s: (
    float(basis_gewig_s) + float(wag_penalty_s)
)
```

`BEREKEN_AFSTAND` bereken die reguitlynafstand tussen twee koördinaatpare.
`BEREKEN_GEWIG` tel basisreistyd en wagtyd in sekondes bymekaar. Roetes
minimaliseer reistyd; afstand in meter word apart langs die gekose roete
opgetel. Die vinnigste roete is dus nie noodwendig die kortste roete in meter nie.

A* gebruik die metriek `afstand(a, b) + 20 × vloerverskil(a, b)`.
Die waarde 20 is hier 'n metriekfaktor, nie 'n beweerde reistyd per vloer nie.
Die skaal is die kleinste verhouding `randgewig / randmetriek` oor alle
rande met 'n positiewe metriek; sonder sulke rande is die skaal nul.
Die heuristiek is `h(n) = skaal × metriek(n, doel)`. Só is elke randkoste
minstens die geskaalde metriek oor daardie rand, wat saam met die
driehoeksongelykheid 'n konsekwente ondergrens vir die gelaaide grafiek gee.
Toetse vergelyk A* se koste met 'n Dijkstra-verwysing.

Ontruiming respekteer randrigtings, toegangsbeperkings en geslote nodusse.

| Gebruikerstipe | Toegang |
|---|---|
| `PUBLIEK` | Openbare gebiede |
| `PERSONEEL` | Openbare, personeel- en intensiewesorggebiede |
| `PASIENT_VERVOER` | Openbare en personeelgebiede |
| `NOODGEVAL` | Alle gedefinieerde toegangsgroepe |

## Bestemmingsindeks

`Boom24` hou hoogstens drie sleutels per nodus en alle blare op dieselfde
diepte. Invoeging verdeel vol nodusse van bo na onder. Die sleutel
`(genormaliseerde_naam, node_id)` onderskei bestemmings met dieselfde naam.

Presiese soek en invoeging verg O(log n) sleutelvergelykings.
`in_volgorde()` lewer geordende sleutel/waarde-pare in O(n).
`soek_metadata()` ondersoek hoogstens alle bestemmings en kos dus O(n)
vir 'n vaste hoeveelheid teks per bestemming. Die boom maak hierdie
gedeeltelike tekssoektog nie logaritmies nie.

Soekterme word met `strip().casefold()` genormaliseer. Naamtreffers kom
eerste; ander metadata-treffers volg. `%` en `_` is letterlike karakters.
SQLite bly die permanente databron. Roep
`grafiek.herbou_bestemmingsindeks()` aan ná veranderinge aan
bestemmingsmetadata, of herbegin die toepassing met databasisbehoud.
Direkte verwydering uit die boom word nie ondersteun nie.

## API-eindpunte

Geboue, vloere en noodkodes word met `insertion_sort()` georden; langer
noduslyste gebruik `merge_sort()`. Beide funksies gee 'n nuwe lys terug,
behou gelyke sleutels se oorspronklike volgorde en aanvaar onder meer 'n
lambda as sorteersleutel. Die admin-API en PNG-vloerplan gebruik hierdie
handgeskrewe algoritmes. Vir 'n vaste drumpel kos saamsmeltsortering
O(n log n); invoegsortering kos O(n²) in die slegste geval.

Die eindpunte en versoekparameters is by `/docs` beskikbaar.

| Metode en pad | Doel | Aanmelding |
|---|---|---|
| `GET /` | Verwelkomingsboodskap | Nee |
| `GET /ui` | Navigasiekoppelvlak | Nee |
| `GET /destinations?q=&limiet=20` | Soek bestemmings; limiet tussen 1 en 100 | Nee |
| `GET /route?begin=&doel=&gebruiker_tipe=PUBLIEK` | Gewone roeteberekening | Nee |
| `GET /route/ontruim?begin=&gebruiker_tipe=PUBLIEK` | Roete na 'n bereikbare nooduitgang | Nee |
| `GET /route/image?begin=&doel=&gebruiker_tipe=PUBLIEK` | Aflaaibare PNG-roetekaart | Nee |
| `GET /incident` | Huidige insident en geblokkeerde nodusse | Nee |
| `GET /admin` | Administrasieblad met aanmeldvorm | Nee |
| `POST /admin/login` | Skep 'n ondertekende sessiekoekie | Aanmeldbewyse |
| `POST /admin/logout` | Verwyder die sessiekoekie | Nee |
| `GET /admin/map` | Geboue, vloere, nodusse en noodkodes | Ja |
| `POST /admin/incident` | Aktiveer of vervang die huidige insident | Ja |
| `DELETE /admin/incident` | Kanselleer die huidige insident | Ja |
| `GET /admin/dekking-kontrole?gebruiker_tipe=PUBLIEK` | Ontruimingsdekking per nodus | Ja |
| `GET /analise/spanboom` | Minimum spanboom of spanwoud | Ja |
| `GET /analise/maks_vloei?bron=&gebruiker_tipe=PUBLIEK` | Gemodelleerde vloei na nooduitgange | Ja |

Voorbeelde:

```text
GET /destinations?q=Radiologie
GET /route?begin=MAIN-G-ENT&doel=SYGEBOU-1-RAD&gebruiker_tipe=PUBLIEK
GET /route/ontruim?begin=MAIN-1-WARDA&gebruiker_tipe=PUBLIEK
```

Die `?` begin die navraagparameters en `&` skei die parameters.

### Insidente en analise

Gewone insidente sluit die gekose nodusse. Kode Rooi aktiveer ontruiming
vir almal; Kode Pink sluit alle nodusse. Aktivering vervang die enkele
bestaande insident.

Dekkingskontrole gebruik afsonderlike werkprosesse om nodusse te ondersoek
en kombineer hul resultate. Prosesopstart en dataoordrag het koste;
parallelle uitvoering waarborg nie 'n spoedwins vir hierdie klein grafiek nie.

Die spanboomanalise behandel die grafiek as 'n ongerigte verbindingsmodel.
Dit is 'n netwerkontwerpberekening, nie 'n roete-instruksie of ontruimingsplan
nie. Vir 'n onsamehangende grafiek word 'n spanwoud teruggegee; die antwoord
meld `is_verbind` en `aantal_komponente`.

Maksimum vloei gebruik randkapasiteite en 'n gesamentlike uitvloei na
nooduitgange. Kapasiteit is 'n ander grootheid as reistyd: 'n vinniger
rand beteken nie outomaties 'n groter kapasiteit nie. Die
demonstrasiekapasiteite stel persone per sekonde voor, maar is nie
gekalibreerde metings nie.
Wanneer die bron reeds 'n uitgang is, dui `reeds_by_uitgang` dit aan.

### HTTP-statuskodes

| Status | Betekenis |
|---|---|
| `200` | Suksesvolle versoek |
| `400` | Onbekende nodus, gebruikerstipe of ongeldige invoer |
| `401` | Aanmelding ontbreek of is ongeldig |
| `403` | Geen toegelate roete vir die gebruiker nie |
| `404` | 'n Gevraagde hulpbron ontbreek |
| `409` | 'n Aktiewe sluiting verhoed die versoek, of geen toegelate ontruimingsvloei is moontlik nie |
| `422` | Vereiste parameters ontbreek of misluk invoervalidering |

## Toetse

Voer die hele toetsstel vanuit die projekgids uit:

```powershell
python -m pytest -q
```

Gebruik `python -m pytest --collect-only -q` om die huidige aantal toetse
te sien. `conftest.py` laat API-toetse hul eie tydelike databasisse gebruik;
dit herskep nie die plaaslike werkdatabasis nie. Die toetse dek onder meer
die 2-4-boom, lambda-formules, toegang, A*, eenrigting-ontruiming,
insidente, grafiekanalise, parallelle dekking en PNG-uitvoer.

Voer die JavaScript-regressietoetse met Node.js uit:

```powershell
node --test test_frontend.mjs
```

Hierdie toetse gebruik 'n nagebootste blaaieromgewing en vervang nie 'n
visuele blaaierkontrole nie. Die ontledingsfunksies is tans API-eindpunte;
die adminblad self bestuur aanmelding en sluitings.

## Git-werkvloei

Haal nuwe takke op en bekyk hulle:

```powershell
git fetch origin
git branch -r
```

Gebruik die projek se boodskapformaat wanneer veranderinge vasgelê word:

```text
# 2025050627 | Function | Beskryf die verandering in Afrikaans
```

Gegenereerde databasisse, tydelike toetslêers, virtuele omgewings en
plaaslike Git-kopieë word deur `.gitignore` uitgesluit. Die openbare
identifiseerders, biblioteekname en bestaande API-velde bly stabiel;
kommentaar en mensleesbare verduidelikings is Afrikaans.
