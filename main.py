"""=====================================================================================
main.py
========
FastAPI-toepassing vir die Hospitaal Navigasiestelsel.

Hierdie lêer definieer alle HTTP-eindpunte en bestuur die toepassingslewensiklus:
  • Databasisvoorbereiding by opstart (herbou indien AUTO_HERBOU_DB=true).
  • Grafiek-voorlading in geheue (HospitaalGrafiek word eenmalig gelaai).
  • Adminaanmelding via 'n ondertekende koekie (HMAC-SHA256).
  • Roeteberekening (A* vir normale navigasie, Dijkstra vir ontruiming).
  • Statieseleêerbediening vir die webkoppelvlak en adminblad.

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
"""

import os
import tempfile
import base64
import hashlib
import hmac
import json
import sqlite3
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from HospitaalGrafiek import HospitaalGrafiek, bou_demo_db
from VloerPlan import teken_vloer_plan

# ---------------------------------------------------------------------------
# Padvariabele — alle lêerpaaie word relatief tot hierdie lêer se gids
# bereken sodat die toepassing vanuit enige gids begin kan word.
# ---------------------------------------------------------------------------
BASE_GIDS  = Path(__file__).resolve().parent
DB_PAD     = BASE_GIDS / "hospitaal.db"
SKEMA_PAD  = BASE_GIDS / "Skema.sql"
SEED_PAD   = BASE_GIDS / "SeedData.sql"

# ---------------------------------------------------------------------------
# Omgewingsveranderlikes — stel via docker-compose.yml of PowerShell.
# NOOIT die verstekwaardes in produksie gebruik nie.
# ---------------------------------------------------------------------------
AUTO_HERBOU_DB       = os.getenv("AUTO_HERBOU_DB", "true").lower() == "true"
ADMIN_GEBRUIKERSNAAM = os.getenv("ADMIN_GEBRUIKERSNAAM", "admin")
ADMIN_WAGWOORD       = os.getenv("ADMIN_WAGWOORD", "admin")
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
    3. Laai die hospitaalgrafiek eenmalig in geheue — alle roeteversoeke
       hergebruik hierdie enkele instansie sonder verdere databasistoegange.
    """
    if AUTO_HERBOU_DB or not DB_PAD.exists():
        bou_demo_db(str(DB_PAD), str(SKEMA_PAD), str(SEED_PAD))
    verseker_insident_skema()
    app.state.grafiek = HospitaalGrafiek(str(DB_PAD))
    yield  # Die toepassing bedien versoeke tussen hier en die einde van die blok.


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
    Konteksbestuurder wat 'n SQLite-verbinding oopmaak, commit by sukses,
    en rollback plus sluiting by 'n fout verseker.
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
            "SELECT node_id FROM insident_nodes WHERE insident_id = 1 ORDER BY node_id"
        ).fetchall()
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
        if inhoud.get("sub") != ADMIN_GEBRUIKERSNAAM or inhoud.get("exp", 0) < time.time():
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
    """
    try:
        insident = kry_insident()
        geblokkeer = set(insident["blocked_node_ids"])

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
    die tyd-optimale teiken is. Hysbakke word verbied; slegs trappe,
    lugbrûe en tonnels word toegelaat (brandveiligheidsprotokol SANS 10400-T).

    Sien HospitaalGrafiek.naaste_veilige_uitgang() vir die algoritme-besonderhede.

    Gee 409 terug as geen veilige roete bereikbaar is nie.
    """
    try:
        insident = kry_insident()
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
            "gebruiker_tipe":        gebruiker_tipe,
            "geskatte_tyd_sekondes": round(tyd_sekondes, 1),
            "geskatte_tyd":          formateer_tyd(tyd_sekondes),
            "geskatte_afstand_m":    round(afstand_m, 1),
            "geskatte_afstand":      formateer_afstand(afstand_m),
            "node_telling":          len(pad),
            "pad":                   pad,
            "incident_active":       insident["active"],
            "avoided_nodes":         insident["blocked_node_ids"],
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
        insident = kry_insident()
        resultaat = app.state.grafiek.astar(
            begin, doel,
            gebruiker_tipe=gebruiker_tipe,
            geblokkeerde_nodes=set(insident["blocked_node_ids"]),
        )
        if resultaat is None:
            raise HTTPException(status_code=403, detail="Geen roete gevind nie.")

        pad, _, _ = resultaat

        # Skep 'n tydelike lêer; delete=False sodat FileResponse dit kan lees
        # voordat BackgroundTask dit verwyder.
        tydelike_leer = tempfile.NamedTemporaryFile(
            prefix="hospitaal_roete_", suffix=".png", delete=False
        )
        uit_pad = Path(tydelike_leer.name)
        tydelike_leer.close()

        teken_vloer_plan(str(DB_PAD), str(uit_pad), verlig_pad=pad)
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

@app.post("/admin/login")
def admin_login(invoer: AdminAanmelding, response: Response):
    """
    Verifieer aanmeldbewyse en stel 'n ondertekende sessie-koekie.

    Gebruik hmac.compare_digest vir timinganval-bestande vergelyking van
    beide die gebruikersnaam en wagwoord.
    """
    gebruiker_ok = hmac.compare_digest(invoer.gebruikersnaam, ADMIN_GEBRUIKERSNAAM)
    wagwoord_ok  = hmac.compare_digest(invoer.wagwoord, ADMIN_WAGWOORD)
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
        geboue = conn.execute(
            "SELECT gebou_id, naam FROM geboue ORDER BY naam"
        ).fetchall()
        resultaat = []
        for gebou in geboue:
            vloere = conn.execute(
                """SELECT vloer_id, naam, level_nommer FROM vloere
                   WHERE gebou_id = ? ORDER BY level_nommer""",
                (gebou["gebou_id"],),
            ).fetchall()
            vloer_data = []
            for vloer in vloere:
                nodes = conn.execute(
                    """SELECT node_id, etiket, tipe_kode, is_nooduitgang FROM nodes
                       WHERE vloer_id = ? ORDER BY etiket""",
                    (vloer["vloer_id"],),
                ).fetchall()
                vloer_data.append({**dict(vloer), "nodes": [dict(n) for n in nodes]})
            resultaat.append({**dict(gebou), "vloere": vloer_data})
        kodes = [dict(ry) for ry in conn.execute(
            "SELECT kode_id, naam, outomaties_modus FROM noodkodes ORDER BY naam"
        ).fetchall()]
        for kode in kodes:
            kode["vooraf_node_ids"] = [
                ry["node_id"]
                for ry in conn.execute(
                    """SELECT node_id FROM noodkode_vooraf_nodes
                       WHERE kode_id = ? ORDER BY node_id""",
                    (kode["kode_id"],),
                ).fetchall()
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
            ontbreek = sorted(set(node_ids) - gevind)
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
