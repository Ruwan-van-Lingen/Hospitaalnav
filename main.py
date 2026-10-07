"""=====================================================================================
main.py
========
FastAPI-toepassing vir die Hospitaal Navigasiestelsel.

Hierdie lêer definieer alle HTTP-eindpunte en bestuur die toepassingslewensiklus:
  • Databasisvoorbereiding by opstart (herbou indien AUTO_HERBOU_DB=true).
  • Grafiek-voorlading in geheue (HospitaalGrafiek word eenmalig gelaai).
  • Adminaanmelding via 'n ondertekende koekie (HMAC-SHA256).
  • Roeteberekening (A* vir normale navigasie, Dijkstra vir ontruiming).
  • Bediening van statiese lêers vir die webkoppelvlak en adminblad.
  • Spanboom-, netwerkvloei- en parallelle ontruimingsontleding.

Eindpunte
----------
  GET  /                  — Verwelkomingsboodskap.
  GET  /ui                — Webkoppelvlak (hospitaal_wayfinder.html).
  GET  /admin             — Adminblad (admin.html).
  GET  /destinations      — Soek navigeerbare bestemmings.
  GET  /incident          — Huidige aktiewe sluiting (openbaar).
  POST /admin/login       — Adminaanmelding.
  POST /admin/logout      — Adminafmelding.
  GET  /admin/map         — Volledige grafieksstruktuur vir die adminblad.
  POST /admin/incident    — Aktiveer 'n nuwe sluiting.
  DELETE /admin/incident  — Kanselleer die aktiewe sluiting.
  GET  /route             — Bereken die kortste toegelate roete (A*).
  GET  /route/ontruim     — Vind die naaste nooduitgang (Dijkstra).
  GET  /route/image       — Bereken roete en lewer as PNG-vloerplan.
  GET  /analise/spanboom  — Minimum spanboom van die infrastruktuur.
  GET  /analise/maks_vloei — Gemodelleerde maksimum vloei na nooduitgange.
  GET  /admin/dekking-kontrole — Parallelle ontruimingskontrole per nodus.
"""

import os
import tempfile
import base64
import hashlib
import hmac
import json
import math
import sqlite3
import time
from contextlib import asynccontextmanager, contextmanager
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from threading import Lock

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from HospitaalGrafiek import (
    HospitaalGrafiek,
    bou_demo_db,
    init_werker,
    kontroleer_alle_nodusse_dekking_parallel,
)
from VloerPlan import teken_vloer_plan
# sorteeralgoritmes
from Sorteer import insertion_sort, merge_sort

# ---------------------------------------------------------------------------
# Padvariabele — alle lêerpaaie word relatief tot hierdie lêer se gids
# bereken sodat die toepassing vanuit enige gids begin kan word.
# ---------------------------------------------------------------------------
BASE_GIDS  = Path(__file__).resolve().parent
DB_PAD     = Path(os.getenv("DB_PAD", str(BASE_GIDS / "hospitaal.db")))
if not DB_PAD.is_absolute():
    DB_PAD = BASE_GIDS / DB_PAD
SKEMA_PAD  = BASE_GIDS / "Skema.sql"
SEED_PAD   = BASE_GIDS / "SeedData.sql"

# ---------------------------------------------------------------------------
# Omgewingsveranderlikes — stel via docker-compose.yml of PowerShell.
# NOOIT die verstekwaardes in produksie gebruik nie.
# ---------------------------------------------------------------------------
AUTO_HERBOU_DB       = os.getenv("AUTO_HERBOU_DB", "true").lower() == "true"
ADMIN_GEBRUIKERSNAAM = os.getenv("ADMIN_GEBRUIKERSNAAM", "admin")
ADMIN_WAGWOORD       = os.getenv("ADMIN_WAGWOORD", "heuningbye123!")
SESSIE_GEHEIM        = os.getenv("SESSIE_GEHEIM", "verander-hierdie-ontwikkelingsgeheim")

# Sessie-instellings
SESSIE_SEKONDES = 60 * 60   # Sessie verval na 1 uur.
SESSIE_KOEKIE   = "hospitaal_admin_sessie"


# ---------------------------------------------------------------------------
# Pydantic-modelle vir versoekliggame
# ---------------------------------------------------------------------------

class AdminAanmelding(BaseModel):
    """Aanmeldbewyse vir die adminblad."""
    gebruikersnaam: str
    wagwoord: str


class InsidentInvoer(BaseModel):
    """
    Invoer vir die aktivering van 'n sluiting.

    node_ids         : Een of meer node-ID's wat as geblokkeer gemerk word.
                       Vir outomatiese noodkodes (sien noodkodes.outomaties_modus)
                       word hierdie veld deur die bediener oorskryf/geïgnoreer,
                       dus mag dit leeg gelaat word.
    ontruimings_modus: Indien True, word die gebruiker na die naaste nooduitgang
                       gestuur (bestemming word geïgnoreer; hysbakke verbied).
                       Word ook deur die bediener afgedwing vir 'n
                       'ONTRUIM_ALMAL'-noodkode, ongeag wat hier gestuur word.
    """
    kode_id: str
    beskrywing: str = Field(default="", max_length=500)
    node_ids: list[str] = Field(default_factory=list)
    ontruimings_modus: bool = False


# ---------------------------------------------------------------------------
# Databasisskema-onderhoud
# ---------------------------------------------------------------------------

def verseker_insident_skema():
    """
    Skep insident-tabelle indien hulle nog nie bestaan nie, en voeg ontbrekende
    kolomme by vir databasis-weergawes wat voor die ontruimingsmodus-funksie
    geskep is. Idempotent — veilig om by elke opstart te roep.
    """
    conn = sqlite3.connect(DB_PAD)
    try:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS noodkodes (
                kode_id TEXT PRIMARY KEY,
                naam TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS aktiewe_insident (
                insident_id INTEGER PRIMARY KEY CHECK (insident_id = 1),
                kode_id TEXT NOT NULL REFERENCES noodkodes (kode_id),
                beskrywing TEXT,
                geaktiveer_op TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ontruimings_modus INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS insident_nodes (
                insident_id INTEGER NOT NULL REFERENCES aktiewe_insident (insident_id) ON DELETE CASCADE,
                node_id TEXT NOT NULL REFERENCES nodes (node_id),
                PRIMARY KEY (insident_id, node_id)
            );

            INSERT OR IGNORE INTO noodkodes (kode_id, naam) VALUES
                ('ONDERHOUD',  'Onderhoud'),
                ('SKOONMAAK',  'Skoonmaak');
            """
        )

        # Migrasiestap: voeg outomaties_modus-kolom by noodkodes as dit in 'n
        # ouer databasisskema ontbreek (sien Skema.sql vir die betekenis van
        # 'ONTRUIM_ALMAL' en 'SLUIT_ALLES').
        kode_cols = {row[1] for row in conn.execute("PRAGMA table_info(noodkodes)")}
        if "outomaties_modus" not in kode_cols:
            conn.execute("ALTER TABLE noodkodes ADD COLUMN outomaties_modus TEXT")

        # Voeg die twee outomatiese noodkodes by (idempotent) — dit gebeur
        # hier eerder as net in SeedData.sql sodat produksiedatabasisse wat
        # AUTO_HERBOU_DB=false gebruik (en dus SeedData.sql nooit weer
        # uitvoer nie) hulle ook by 'n opstart-migrasie kry.
        conn.execute(
            """INSERT OR IGNORE INTO noodkodes (kode_id, naam, outomaties_modus) VALUES
                ('ROOI', 'Kode Rooi — Brand (ontruim almal)', 'ONTRUIM_ALMAL'),
                ('PINK', 'Kode Pink — Ontvoering (algehele grendel)', 'SLUIT_ALLES')"""
        )

        # Verwyder afgetrede noodkodes, insluitend enige ou aktiewe insident
        # wat nog daarna verwys, sodat hulle nie via die API gebruik kan word nie.
        conn.execute(
            "DELETE FROM aktiewe_insident WHERE kode_id IN ('GEEL', 'SEKURITEIT')"
        )
        conn.execute("DELETE FROM noodkodes WHERE kode_id IN ('GEEL', 'SEKURITEIT')")

        conn.execute(
            """CREATE TABLE IF NOT EXISTS noodkode_vooraf_nodes (
                   kode_id TEXT NOT NULL REFERENCES noodkodes (kode_id) ON DELETE CASCADE,
                   node_id TEXT NOT NULL REFERENCES nodes (node_id),
                   PRIMARY KEY (kode_id, node_id)
               )"""
        )
        conn.executemany(
            "INSERT OR IGNORE INTO noodkode_vooraf_nodes (kode_id, node_id) VALUES (?, ?)",
            [
                ("ONDERHOUD", "MAIN-G-ELV"),
                ("ONDERHOUD", "MAIN-1-ELV"),
                ("ONDERHOUD", "MAIN-2-ELV"),
                ("ONDERHOUD", "SYGEBOU-G-ELV"),
                ("ONDERHOUD", "SYGEBOU-1-ELV"),
                ("SKOONMAAK", "MAIN-1-WARDA"),
                ("SKOONMAAK", "MAIN-1-WARDB"),
                ("SKOONMAAK", "MAIN-2-OR"),
            ],
        )

        # Migrasiestap: voeg ontruimings_modus-kolom by as dit in 'n ouer
        # databasisskema ontbreek.
        cols = {row[1] for row in conn.execute("PRAGMA table_info(aktiewe_insident)")}
        if "ontruimings_modus" not in cols:
            conn.execute(
                "ALTER TABLE aktiewe_insident ADD COLUMN ontruimings_modus INTEGER NOT NULL DEFAULT 0"
            )

        # Migrasiestap: voeg is_nooduitgang-kolom by nodes as dit ontbreek.
        node_cols = {row[1] for row in conn.execute("PRAGMA table_info(nodes)")}
        if "is_nooduitgang" not in node_cols:
            conn.execute(
                "ALTER TABLE nodes ADD COLUMN is_nooduitgang INTEGER NOT NULL DEFAULT 0"
            )

        # Ouer databasisse gebruik die randtipe se demonstrasiekapasiteit
        # totdat 'n gemete kapasiteit uitdruklik gestoor word.
        rand_cols = {row[1] for row in conn.execute("PRAGMA table_info(rande)")}
        if "kapasiteit" not in rand_cols:
            conn.execute("ALTER TABLE rande ADD COLUMN kapasiteit REAL")

        conn.commit()
    finally:
        conn.close()


def verseker_seed_data():
    """Voeg ontbrekende standaardnodusse en -rande uit SeedData.sql by.

    SeedData.sql gebruik idempotente ``INSERT OR IGNORE``-stellings. Daarom kan
    hierdie migrasie ook op 'n bestaande, aanhoudende Docker-databasis loop
    sonder om insidente of ander bestaande data uit te vee.
    """
    conn = sqlite3.connect(DB_PAD)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SEED_PAD.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Toepassingslewensiklus
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan-hanteerder: voorbereiding voor die eerste versoek.

    1. Bou (of herbou) die SQLite-databasis uit Skema.sql + SeedData.sql.
    2. Verseker dat insident-tabelle en nuwe kolomme bestaan.
    3. Voeg ontbrekende standaardnodusse en -rande uit SeedData.sql by.
    4. Laai die hospitaalgrafiek eenmalig in geheue — alle roeteversoeke
       hergebruik hierdie instansie. Toegangsregte en insidente word apart gelees.
    """
    DB_PAD.parent.mkdir(parents=True, exist_ok=True)
    if AUTO_HERBOU_DB or not DB_PAD.exists():
        bou_demo_db(str(DB_PAD), str(SKEMA_PAD), str(SEED_PAD))
    verseker_insident_skema()
    verseker_seed_data()
    app.state.grafiek = HospitaalGrafiek(str(DB_PAD))
    app.state.dekking_pool = None
    app.state.dekking_slot = Lock()
    try:
        yield  # Bedien versoeke nadat die grafiek gereed is.
    finally:
        if app.state.dekking_pool is not None:
            app.state.dekking_pool.shutdown(wait=True)
            app.state.dekking_pool = None


def kry_dekking_pool(app: FastAPI) -> ProcessPoolExecutor:
    """Skep hoogstens een begrensde werkprosespoel per toepassing.

    Die slot voorkom dubbele poele by gelyktydige eerste versoeke. Elke
    werkproses laai sy eie grafiek eenmalig; gewone roetes benodig geen poel nie.
    """
    with app.state.dekking_slot:
        if app.state.dekking_pool is None:
            app.state.dekking_pool = ProcessPoolExecutor(
                max_workers=min(4, os.cpu_count() or 1),
                # Begin vars prosesse op elke platform. Linux se fork vanuit
                # die bediener se werksdrade kan geërfde slotte laat vashaak.
                mp_context=get_context("spawn"),
                initializer=init_werker,
                initargs=(str(DB_PAD),),
            )
        return app.state.dekking_pool


app = FastAPI(
    title="Hospitaal Navigasie API",
    description="Bereken die kortste en toeganklikste roetes in die hospitaalkampus.",
    lifespan=lifespan,
)

# CORS-middleware: laat die webkoppelvlak toe om die API vanaf 'n ander
# poort te bereik (byvoorbeeld tydens plaaslike ontwikkeling op poort 5500).
# Beperk allow_origins tot bekende adresse voordat die API in produksie ontplooi word.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Hulpfunksies
# ---------------------------------------------------------------------------

def formateer_tyd(sekondes: float) -> str:
    """Formateer sekondes as mensleesbare tydstring, byvoorbeeld '1m 23s' of '2h 3m 4s'."""
    totaal = max(0, round(sekondes))
    ure, oor = divmod(totaal, 3600)
    minute, sekondes_oor = divmod(oor, 60)
    dele = []
    if ure:
        dele.append(f"{ure}h")
    if minute or ure:
        dele.append(f"{minute}m")
    dele.append(f"{sekondes_oor}s")
    return " ".join(dele)


def formateer_afstand(meter: float) -> str:
    """Formateer meter as '45m' of '1.2km'."""
    meter = max(0.0, meter)
    if meter >= 1000:
        return f"{meter / 1000:.1f}km"
    return f"{round(meter)}m"


@contextmanager
def db_verbinding():
    """
    Open 'n SQLite-verbinding en bevestig veranderinge by sukses.
    Rol die transaksie terug by 'n fout en sluit altyd die verbinding.
    """
    conn = sqlite3.connect(DB_PAD)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def kry_insident() -> dict:
    """
    Lees die huidige aktiewe insident uit die databasis.

    Gee altyd 'n woordeboek terug, selfs as geen insident aktief is nie
    (active=False, blocked_node_ids=[], ontruimings_modus=False).
    Word gebruik deur beide die openbare /incident eindpunt en intern
    deur roeteberekening.
    """
    with db_verbinding() as conn:
        ry = conn.execute(
            """
            SELECT ai.kode_id, nk.naam, ai.beskrywing,
                   ai.geaktiveer_op, ai.ontruimings_modus, nk.outomaties_modus
            FROM aktiewe_insident ai
            JOIN noodkodes nk ON nk.kode_id = ai.kode_id
            WHERE ai.insident_id = 1
            """
        ).fetchone()
        if ry is None:
            return {"active": False, "blocked_node_ids": [], "ontruimings_modus": False}
        node_rye = conn.execute(
            "SELECT node_id FROM insident_nodes WHERE insident_id = 1"
        ).fetchall()
        # Saamsmeltsortering: hierdie lys groei saam met die hospitaal. By 'n
        # Kode Pink (SLUIT_ALLES) bevat dit ELKE nodus in die gebou, dus is
        # O(n log n) hier die regte keuse.
        node_rye = merge_sort(node_rye, sleutel="node_id")
    return {
        "active":           True,
        "code":             ry["kode_id"],
        "name":             ry["naam"],
        "description":      ry["beskrywing"] or "",
        "activated_at":     ry["geaktiveer_op"],
        "blocked_node_ids": [r["node_id"] for r in node_rye],
        # Die ontruimings_modus-vlag word deur die webkoppelvlak gebruik om
        # /route/ontruim eerder as /route aan te roep.
        "ontruimings_modus": bool(ry["ontruimings_modus"]),
        # 'ONTRUIM_ALMAL', 'SLUIT_ALLES' of None — laat die admin- en
        # webkoppelvlak toe om outomaties-geaktiveerde insidente anders te
        # vertoon (bv. "Algehele grendel aktief" i.p.v. 'n rou nodus-telling).
        "outomaties_modus": ry["outomaties_modus"],
    }


# ---------------------------------------------------------------------------
# Sessiebestuur (HMAC-ondertekende koekie)
# ---------------------------------------------------------------------------

def skep_sessie() -> str:
    """
    Skep 'n HMAC-SHA256-ondertekende sessie-token.

    Die token bestaan uit twee dele geskei deur 'n punt:
      base64({"sub": gebruikersnaam, "exp": vervaltydstip}) . HMAC-handtekening

    Geen databasis word benodig nie — die handtekening bevestig egtheid en
    die vervaltydstip voorkom hergebruik van oue tokens.
    """
    inhoud = json.dumps(
        {"sub": ADMIN_GEBRUIKERSNAAM, "exp": int(time.time()) + SESSIE_SEKONDES},
        separators=(",", ":"),
    ).encode()
    data = base64.urlsafe_b64encode(inhoud).decode().rstrip("=")
    handtekening = hmac.new(SESSIE_GEHEIM.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{handtekening}"


def vereis_admin(hospitaal_admin_sessie: str | None = Cookie(default=None)) -> str:
    """
    FastAPI-afhanklikheid wat 'n geldige adminsessie-koekie vereis.

    Verwerp versoeke met 401 as die koekie ontbreek, vervals is of verval het.
    Word gebruik as 'n Depends()-argument op alle beskermde eindpunte.
    """
    if not hospitaal_admin_sessie:
        raise HTTPException(status_code=401, detail="Adminaanmelding word vereis.")
    try:
        data, handtekening = hospitaal_admin_sessie.rsplit(".", 1)
        verwag = hmac.new(SESSIE_GEHEIM.encode(), data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(handtekening, verwag):
            raise ValueError
        inhoud = json.loads(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)))
        if not isinstance(inhoud, dict):
            raise ValueError
        verval = inhoud.get("exp", 0)
        if not isinstance(verval, (int, float)) or not math.isfinite(verval):
            raise ValueError
        if inhoud.get("sub") != ADMIN_GEBRUIKERSNAAM or verval <= time.time():
            raise ValueError
        return inhoud["sub"]
    except (ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Die adminsessie is ongeldig of het verval.")


# ---------------------------------------------------------------------------
# Statiese lêer-eindpunte
# ---------------------------------------------------------------------------

@app.get("/")
def tuisblad():
    return {"boodskap": "Welkom by die Hospitaal Navigasie API. Gaan na /docs vir die dokumentasie."}


@app.get("/ui")
def ui():
    """Bedien die interaktiewe webkoppelvlak direk vanaf dieselfde API-adres."""
    html_pad = BASE_GIDS / "hospitaal_wayfinder.html"
    if not html_pad.exists():
        raise HTTPException(status_code=404, detail="hospitaal_wayfinder.html nie gevind nie.")
    return FileResponse(str(html_pad))


@app.get("/admin")
def admin_ui():
    """Bedien die adminblad vir sluitingsbestuur."""
    html_pad = BASE_GIDS / "admin.html"
    if not html_pad.exists():
        raise HTTPException(status_code=404, detail="admin.html nie gevind nie.")
    return FileResponse(str(html_pad))


@app.get("/admin.css", include_in_schema=False)
def admin_css():
    return FileResponse(str(BASE_GIDS / "admin.css"), media_type="text/css")


@app.get("/admin.js", include_in_schema=False)
def admin_javascript():
    return FileResponse(str(BASE_GIDS / "admin.js"), media_type="text/javascript")


@app.get("/hospitaal_wayfinder.css", include_in_schema=False)
def ui_css():
    """Bedien die webkoppelvlak se stylblad."""
    css_pad = BASE_GIDS / "hospitaal_wayfinder.css"
    if not css_pad.exists():
        raise HTTPException(status_code=404, detail="hospitaal_wayfinder.css nie gevind nie.")
    return FileResponse(str(css_pad), media_type="text/css")


@app.get("/hospitaal_wayfinder.js", include_in_schema=False)
def ui_javascript():
    """Bedien die webkoppelvlak se JavaScript."""
    js_pad = BASE_GIDS / "hospitaal_wayfinder.js"
    if not js_pad.exists():
        raise HTTPException(status_code=404, detail="hospitaal_wayfinder.js nie gevind nie.")
    return FileResponse(str(js_pad), media_type="text/javascript")


# ---------------------------------------------------------------------------
# Openbare navigasie-eindpunte
# ---------------------------------------------------------------------------

@app.get("/destinations")
def soek_bestemmings(
    q: str = Query("", description="Naam, node-ID, tipe, gebou of vloer"),
    limiet: int = Query(20, ge=1, le=100),
):
    """
    Soek mensleesbare bestemmings vir die webkoppelvlak se soekvelde.

    Laat besoekers toe om na 'Radiologie' te soek sonder dat hulle
    'SYGEBOU-1-RAD' hoef te ken. Die soektog is kas-onsensitief.
    """
    return {
        "soekterm": q,
        "bestemmings": app.state.grafiek.soek_bestemmings(q, limiet),
    }


@app.get("/incident")
def lees_insident():
    """
    Gee die huidige sluiting aan die openbare webkoppelvlak terug.

    Die webkoppelvlak gebruik hierdie eindpunt by laai om:
      • Die rooi insidentbanier te wys as active=True.
      • Geslote nodusse in die seleksielys te deaktiveer.
      • Ontruimingsmodus te aktiveer (verander /route-aanroep na /route/ontruim).
    """
    return kry_insident()


@app.get("/route")
def kry_roete(
    begin: str = Query(..., description="Die beginnode se ID (bv. MAIN-G-ENT)"),
    doel: str = Query(..., description="Die eindnode se ID (bv. SYGEBOU-1-RAD)"),
    gebruiker_tipe: str = Query("PUBLIEK", description="Gebruikerstipe: PUBLIEK, PERSONEEL, PASIENT_VERVOER of NOODGEVAL"),
):
    """
    Bereken die tyd-optimale toegelate roete met A*.

    Gee 409 terug as die begin- of doelpunt geblokkeer is.
    Gee 403 terug as geen toegelate pad bestaan vir die gebruikerstipe.
    A* omseil outomaties enige nodusse wat deur die aktiewe insident geblokkeer is.
    Tydens ontruimingsmodus bepaal Dijkstra die uitgang; doel word geïgnoreer.
    """
    try:
        insident = kry_insident()
        geblokkeer = set(insident["blocked_node_ids"])

        if insident["ontruimings_modus"]:
            return bereken_ontruimingsroete(begin, gebruiker_tipe, insident)

        # Kyk vroeg of die eksplisiete begin- of doelpunt self geblokkeer is —
        # A* sou dit ook vind, maar hierdie kontrole gee 'n duideliker foutboodskap.
        if begin in geblokkeer:
            raise HTTPException(status_code=409, detail="Die beginpunt is binne die geslote gebied.")
        if doel in geblokkeer:
            raise HTTPException(status_code=409, detail="Die bestemming is tydelik gesluit.")

        resultaat = app.state.grafiek.astar(
            begin, doel,
            gebruiker_tipe=gebruiker_tipe,
            geblokkeerde_nodes=geblokkeer,
        )

        if resultaat is None:
            raise HTTPException(
                status_code=409 if insident["active"] else 403,
                detail=(
                    "Geen beskikbare roete om die huidige sluiting nie."
                    if insident["active"]
                    else "Geen roete gevind nie. Die pad bestaan nie of jy het nie toegang nie."
                ),
            )

        pad, tyd_sekondes, afstand_m = resultaat
        return {
            "begin_node":            begin,
            "doel_node":             doel,
            "gebruiker_tipe":        gebruiker_tipe,
            "geskatte_tyd_sekondes": round(tyd_sekondes, 1),
            "geskatte_tyd":          formateer_tyd(tyd_sekondes),
            "geskatte_afstand_m":    round(afstand_m, 1),
            "geskatte_afstand":      formateer_afstand(afstand_m),
            "node_telling":          len(pad),
            "pad":                   pad,
            "incident_active":       insident["active"],
            "incident_code":         insident.get("code"),
            "avoided_nodes":         insident["blocked_node_ids"],
            "ontruimings_modus":     False,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/route/ontruim")
def kry_ontruimingsroete(
    begin: str = Query(..., description="Die beginpunt se node-ID"),
    gebruiker_tipe: str = Query("PUBLIEK", description="Gebruikerstipe"),
):
    """
    Ontruimingsmodus: vind die naaste veilige nooduitgang met multi-bron Dijkstra.

    Die gebruiker se gewenste bestemming word GEÏGNOREER — die algoritme
    bepaal self watter nooduitgang (is_nooduitgang=1 in die databasis)
    die tyd-optimale teiken is. Hysbakke word uitgesluit. Hierdie
    demonstrasiemodel is nie 'n gesertifiseerde ontruimingsplan nie.

    Sien HospitaalGrafiek.naaste_veilige_uitgang() vir die algoritme-besonderhede.

    Gee 409 terug as geen veilige roete bereikbaar is nie.
    """
    return bereken_ontruimingsroete(begin, gebruiker_tipe, kry_insident())


def bereken_ontruimingsroete(begin: str, gebruiker_tipe: str, insident: dict) -> dict:
    """Gebruik dieselfde insidentmomentopname vir gewone en noodroeteversoeke."""
    try:
        geblokkeer = set(insident["blocked_node_ids"])

        if begin in geblokkeer:
            raise HTTPException(
                status_code=409,
                detail="Die beginpunt is binne die geslote gebied; ontruiming is nie moontlik nie.",
            )

        resultaat = app.state.grafiek.naaste_veilige_uitgang(
            begin,
            gebruiker_tipe=gebruiker_tipe,
            geblokkeerde_nodes=geblokkeer,
        )

        if resultaat is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Geen veilige ontruimingsroete beskikbaar nie. "
                    "Alle nooduitgange is geblokkeer of onbereikbaar."
                ),
            )

        pad, tyd_sekondes, afstand_m = resultaat
        uitgang_node = pad[-1]  # Die laaste nodus in die pad is die bereikte nooduitgang.

        return {
            "begin_node":            begin,
            "uitgang_node":          uitgang_node,
            "doel_node":             uitgang_node,
            "gebruiker_tipe":        gebruiker_tipe,
            "geskatte_tyd_sekondes": round(tyd_sekondes, 1),
            "geskatte_tyd":          formateer_tyd(tyd_sekondes),
            "geskatte_afstand_m":    round(afstand_m, 1),
            "geskatte_afstand":      formateer_afstand(afstand_m),
            "node_telling":          len(pad),
            "pad":                   pad,
            "incident_active":       insident["active"],
            "avoided_nodes":         insident["blocked_node_ids"],
            "incident_code":         insident.get("code"),
            "ontruimings_modus":     True,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/route/image")
def kry_roete_prentjie(
    begin: str = Query(..., description="Die beginnodus se ID (bv. MAIN-G-ENT)"),
    doel: str = Query(..., description="Die eindnodus se ID (bv. SYGEBOU-1-RAD)"),
    gebruiker_tipe: str = Query("PUBLIEK", description="Gebruikerstipe"),
):
    """
    Bereken 'n roete en lewer die vloerplan as 'n aflaaibare PNG-prent.

    Die PNG word in 'n tydelike lêer gestoor en via FileResponse gestuur.
    BackgroundTask verwyder die lêer outomaties nadat die HTTP-antwoord
    versend is, sodat geen tydelike lêers agtergelaat word nie.
    """
    try:
        # Dieselfde toegangs-, sluitings- en ontruimingsreëls as die JSON-roete.
        roete = kry_roete(begin, doel, gebruiker_tipe)

        # Skep 'n tydelike lêer; delete=False sodat FileResponse dit kan lees
        # voordat BackgroundTask dit verwyder.
        tydelike_leer = tempfile.NamedTemporaryFile(
            prefix="hospitaal_roete_", suffix=".png", delete=False
        )
        uit_pad = Path(tydelike_leer.name)
        tydelike_leer.close()

        try:
            teken_vloer_plan(str(DB_PAD), str(uit_pad), verlig_pad=roete["pad"])
        except Exception:
            uit_pad.unlink(missing_ok=True)
            raise
        return FileResponse(
            uit_pad,
            media_type="image/png",
            filename="hospitaal_roete.png",
            background=BackgroundTask(uit_pad.unlink, missing_ok=True),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Adminbeskermde eindpunte
# ---------------------------------------------------------------------------

@app.get("/analise/spanboom")
def kry_min_spanboom(_: str = Depends(vereis_admin)):
    """Ontleed ongerigte infrastruktuur sonder gebruiker- of insidentfilters.

    'n Ontkoppelde grafiek lewer 'n minimum spanwoud, nie 'n enkele spanboom nie.
    Hierdie ontleding bereken nie 'n navigasie- of ontruimingsroete nie.
    """
    kante, gewig = app.state.grafiek.bereken_min_spanboom()
    aantal_nodusse = len(app.state.grafiek.nodes)
    komponente = aantal_nodusse - len(kante)
    return {
        "totale_gewig_s": round(gewig, 1),
        "totale_gewig": formateer_tyd(gewig),
        "aantal_kante": len(kante),
        "aantal_nodusse": aantal_nodusse,
        "aantal_komponente": komponente,
        "is_verbind": komponente == 1,
        "kante": [{"van": a, "na": b, "gewig_s": w} for a, b, w in kante],
    }


@app.get("/analise/maks_vloei")
def kry_maks_vloei(
    bron: str = Query(..., description="Die bronpunt se node-ID"),
    gebruiker_tipe: str = Query("PUBLIEK", description="Gebruikerstipe"),
    _: str = Depends(vereis_admin),
):
    """Bereken gemodelleerde deurvloei; kapasiteite is demonstrasiewaardes.

    Respekteer die aktiewe sluiting en toegangsregte en sluit hysbakke uit.
    Nul met reeds_by_uitgang=True beteken geen verdere netwerkreis is nodig nie.
    """
    insident = kry_insident()
    try:
        resultaat = app.state.grafiek.maks_vloei_na_uitgange(
            bron, gebruiker_tipe, set(insident["blocked_node_ids"])
        )
    except ValueError as fout:
        raise HTTPException(status_code=400, detail=str(fout))
    if resultaat is None:
        raise HTTPException(
            status_code=409,
            detail="Geen toegelate ontruimingsvloei vanaf hierdie bronpunt is beskikbaar nie.",
        )
    vloei, bottelnekke = resultaat
    return {
        "bron_node": bron,
        "gebruiker_tipe": gebruiker_tipe,
        "maks_vloei_persone_per_s": round(vloei, 2),
        "reeds_by_uitgang": app.state.grafiek.nodes[bron]["is_nooduitgang"],
        "bottelnek_kante": [
            {"van": a, "na": b, "kapasiteit": k} for a, b, k in bottelnekke
        ],
        "incident_active": insident["active"],
        "avoided_nodes": insident["blocked_node_ids"],
    }


@app.get("/admin/dekking-kontrole")
def dekking_kontrole(
    gebruiker_tipe: str = Query("PUBLIEK", description="Gebruikerstipe vir ontruimingstoegang"),
    _: str = Depends(vereis_admin),
):
    """Kontroleer elke nodus se ontruimingsdekking in herbruikbare werkprosesse.

    Die ontleding is leesalleen. Elke werktaak ontvang dieselfde momentopname
    van die huidige sluiting sodat die resultate onderling vergelykbaar is.
    """
    try:
        # Valideer vóór die poel geskep word, selfs as alle nodusse gesluit is.
        app.state.grafiek.toegelate_groepe(gebruiker_tipe)
    except ValueError as fout:
        raise HTTPException(status_code=400, detail=str(fout))
    insident = kry_insident()
    resultate = kontroleer_alle_nodusse_dekking_parallel(
        list(app.state.grafiek.nodes),
        gebruiker_tipe,
        set(insident["blocked_node_ids"]),
        kry_dekking_pool(app),
    )
    onbereikbaar = [r for r in resultate if not r["bereikbaar"]]
    return {
        "gebruiker_tipe": gebruiker_tipe,
        "incident_active": insident["active"],
        "totaal_nodusse": len(resultate),
        "onbereikbaar_telling": len(onbereikbaar),
        "onbereikbaar": onbereikbaar,
        "alle_resultate": resultate,
    }


@app.post("/admin/login")
def admin_login(invoer: AdminAanmelding, response: Response):
    """
    Verifieer aanmeldbewyse en stel 'n ondertekende sessie-koekie.

    Gebruik hmac.compare_digest vir timinganval-bestande vergelyking van
    beide die gebruikersnaam en wagwoord.
    """
    gebruiker_ok = hmac.compare_digest(invoer.gebruikersnaam.encode(), ADMIN_GEBRUIKERSNAAM.encode())
    wagwoord_ok  = hmac.compare_digest(invoer.wagwoord.encode(), ADMIN_WAGWOORD.encode())
    if not (gebruiker_ok and wagwoord_ok):
        raise HTTPException(status_code=401, detail="Verkeerde gebruikersnaam of wagwoord.")
    response.set_cookie(
        SESSIE_KOEKIE,
        skep_sessie(),
        max_age=SESSIE_SEKONDES,
        httponly=True,   # Voorkom JavaScript-toegang tot die koekie.
        samesite="strict",
        secure=False,    # Stel op True vir HTTPS in produksie.
    )
    return {"message": "Aanmelding suksesvol."}


@app.post("/admin/logout")
def admin_logout(response: Response):
    """Verwyder die sessie-koekie om die gebruiker af te meld."""
    response.delete_cookie(SESSIE_KOEKIE)
    return {"message": "Afgemeld."}


@app.get("/admin/map")
def admin_kaart(_: str = Depends(vereis_admin)):
    """
    Gee die volledige grafieksstruktuur terug vir die adminblad se keusestruktuur.

    Sluit in: geboue → vloere → nodusse (met is_nooduitgang-vlag),
    noodkodes vir die keuselys, en die huidige aktiewe insident.
    """
    with db_verbinding() as conn:
        # Invoegsortering: die hospitaal het 'n handvol geboue (tans twee) en
        # hierdie lys sal volgens sy aard nooit groot word nie.
        geboue = insertion_sort(
            conn.execute("SELECT gebou_id, naam FROM geboue").fetchall(),
            sleutel="naam",
        )
        resultaat = []
        for gebou in geboue:
            # Invoegsortering: vloere per gebou is 'n klein lys (tans 3 en 2).
            vloere = insertion_sort(
                conn.execute(
                    """SELECT vloer_id, naam, level_nommer FROM vloere
                       WHERE gebou_id = ?""",
                    (gebou["gebou_id"],),
                ).fetchall(),
                sleutel="level_nommer",
            )
            vloer_data = []
            for vloer in vloere:
                # Saamsmeltsortering: nodusse per vloer is die lys wat die
                # meeste groei. Die demodata het 3 tot 7 per vloer, maar 'n
                # werklike hospitaalvloer het maklik 'n paar honderd
                # besluitspunte, dus is O(n log n) hier die veilige keuse.
                nodes = merge_sort(
                    conn.execute(
                        """SELECT node_id, etiket, tipe_kode, is_nooduitgang FROM nodes
                           WHERE vloer_id = ?""",
                        (vloer["vloer_id"],),
                    ).fetchall(),
                    sleutel="etiket",
                )
                vloer_data.append({**dict(vloer), "nodes": [dict(n) for n in nodes]})
            resultaat.append({**dict(gebou), "vloere": vloer_data})

        # Invoegsortering: daar is vier noodkodes en dit is 'n vaste lys.
        kodes = [dict(ry) for ry in insertion_sort(
            conn.execute(
                "SELECT kode_id, naam, outomaties_modus FROM noodkodes"
            ).fetchall(),
            sleutel="naam",
        )]
        for kode in kodes:
            # Invoegsortering: hoogstens 'n paar voorafgekose nodusse per kode.
            kode["vooraf_node_ids"] = [
                ry["node_id"]
                for ry in insertion_sort(
                    conn.execute(
                        """SELECT node_id FROM noodkode_vooraf_nodes
                           WHERE kode_id = ?""",
                        (kode["kode_id"],),
                    ).fetchall(),
                    sleutel="node_id",
                )
            ]
    return {"geboue": resultaat, "noodkodes": kodes, "incident": kry_insident()}


@app.post("/admin/incident")
def aktiveer_insident(invoer: InsidentInvoer, _: str = Depends(vereis_admin)):
    """
    Aktiveer 'n nuwe sluiting.

    Vervang enige bestaande aktiewe insident (slegs een insident op 'n slag).
    Vir gewone (handmatige) noodkodes word invoer.node_ids gebruik en teen
    die databasis gevalideer, presies soos voorheen.

    Vir OUTOMATIESE noodkodes (noodkodes.outomaties_modus) word die
    kliënt se node_ids/ontruimings_modus geïgnoreer en deur die bediener
    self bepaal — dit verseker dat 'n Kode Rooi/Pink altyd dieselfde
    waarborg gee ongeag wat die admin-webblad toevallig gestuur het:
      • 'ONTRUIM_ALMAL' (bv. Kode Rooi/brand): geen nodusse word geblokkeer
        nie, maar ontruimings_modus word geforseer AAN — elke gebruiker
        word na die naaste nooduitgang gestuur.
      • 'SLUIT_ALLES' (bv. Kode Pink/algehele grendel): ELKE nodus in die
        hospitaal word geblokkeer — geen roete is moontlik totdat die
        insident gekanselleer word nie.
    """
    with db_verbinding() as conn:
        kode = conn.execute(
            "SELECT outomaties_modus FROM noodkodes WHERE kode_id = ?", (invoer.kode_id,)
        ).fetchone()
        if kode is None:
            raise HTTPException(status_code=400, detail="Ongeldige noodkode.")
        outomaties_modus = kode["outomaties_modus"]

        # Verwyder duplikate terwyl die volgorde behou word.
        node_ids = list(dict.fromkeys(invoer.node_ids))
        ontruimings_modus = invoer.ontruimings_modus

        if outomaties_modus == "ONTRUIM_ALMAL":
            node_ids = []
            ontruimings_modus = True
        elif outomaties_modus == "SLUIT_ALLES":
            node_ids = [r["node_id"] for r in conn.execute("SELECT node_id FROM nodes")]
            ontruimings_modus = False
        else:
            # Gewone handmatige sluiting: minstens een nodus word vereis,
            # en elke node-ID moet in die databasis bestaan.
            if not node_ids:
                raise HTTPException(
                    status_code=400,
                    detail="Kies minstens een nodus vir hierdie sluitingstipe.",
                )
            plekhouers = ",".join("?" for _ in node_ids)
            gevind = {
                ry["node_id"]
                for ry in conn.execute(
                    f"SELECT node_id FROM nodes WHERE node_id IN ({plekhouers})", node_ids
                ).fetchall()
            }
            # Invoegsortering: hierdie lys is die inhoud van 'n foutboodskap
            # en is byna altyd leeg of net 'n paar items lank.
            ontbreek = insertion_sort(set(node_ids) - gevind)
            if ontbreek:
                raise HTTPException(
                    status_code=400,
                    detail=f"Onbekende node-ID(s): {', '.join(ontbreek)}",
                )

        # Vervang die huidige insident (DELETE + INSERT verseker dat slegs een
        # insident met insident_id=1 op 'n slag kan bestaan).
        conn.execute("DELETE FROM aktiewe_insident")
        conn.execute(
            """INSERT INTO aktiewe_insident (insident_id, kode_id, beskrywing, ontruimings_modus)
               VALUES (1, ?, ?, ?)""",
            (invoer.kode_id, invoer.beskrywing.strip(), int(ontruimings_modus)),
        )
        conn.executemany(
            "INSERT INTO insident_nodes (insident_id, node_id) VALUES (1, ?)",
            [(node_id,) for node_id in node_ids],
        )
    return kry_insident()


@app.delete("/admin/incident")
def kanselleer_insident(_: str = Depends(vereis_admin)):
    """
    Kanselleer die aktiewe insident.

    CASCADE DELETE in die skema verwyder ook alle verwante insident_nodes
    outomaties wanneer die aktiewe_insident-ry verwyder word.
    """
    with db_verbinding() as conn:
        conn.execute("DELETE FROM aktiewe_insident")
    return {"active": False, "blocked_node_ids": []}
