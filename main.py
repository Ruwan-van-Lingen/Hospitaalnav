"""==========================================================================

============================================================================"""

# main.py
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
from HospitaalGrafiek import HospitaalGrafiek, bou_demo_db
from starlette.background import BackgroundTask
from VloerPlan import teken_vloer_plan

BASE_GIDS = Path(__file__).resolve().parent
DB_PAD = BASE_GIDS / "hospitaal.db"
SKEMA_PAD = BASE_GIDS / "Skema.sql"
SEED_PAD = BASE_GIDS / "SeedData.sql"
AUTO_HERBOU_DB = os.getenv("AUTO_HERBOU_DB", "true").lower() == "true"
ADMIN_GEBRUIKERSNAAM = os.getenv("ADMIN_GEBRUIKERSNAAM", "admin")
ADMIN_WAGWOORD = os.getenv("ADMIN_WAGWOORD", "admin")
SESSIE_GEHEIM = os.getenv("SESSIE_GEHEIM", "verander-hierdie-ontwikkelingsgeheim")
SESSIE_SEKONDES = 60 * 60
SESSIE_KOEKIE = "hospitaal_admin_sessie"


class AdminAanmelding(BaseModel):
    gebruikersnaam: str
    wagwoord: str


class InsidentInvoer(BaseModel):
    kode_id: str
    beskrywing: str = Field(default="", max_length=500)
    node_ids: list[str] = Field(min_length=1)


def verseker_insident_skema():
    """Voeg die MVP-tabelle by 'n bestaande databasis sonder dat data verlore gaan."""
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
                geaktiveer_op TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS insident_nodes (
                insident_id INTEGER NOT NULL REFERENCES aktiewe_insident (insident_id) ON DELETE CASCADE,
                node_id TEXT NOT NULL REFERENCES nodes (node_id),
                PRIMARY KEY (insident_id, node_id)
            );
            INSERT OR IGNORE INTO noodkodes (kode_id, naam) VALUES
                ('ONDERHOUD', 'Onderhoud'),
                ('SKOONMAAK', 'Skoonmaak'),
                ('GEEL', 'Gevaarlike materiaal'),
                ('SEKURITEIT', 'Sekuriteitsvoorval');
            """
        )
        conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Berei die databasis en grafiek voor voordat die API versoeke ontvang."""
    # Herbou die databasis by elke begin tydens ontwikkeling.
    # AUTO_HERBOU_DB=false om bestaande data in 'n produksie-omgewing te behou.
    if AUTO_HERBOU_DB or not DB_PAD.exists():
        bou_demo_db(str(DB_PAD), str(SKEMA_PAD), str(SEED_PAD))
    verseker_insident_skema()

    # Laai die grafiek een keer in die toepassingsgeheue vir hergebruik.
    app.state.grafiek = HospitaalGrafiek(str(DB_PAD))
    yield


app = FastAPI(
    title="Hospitaal Navigasie API",
    description="API vir die berekening van die kortste en toeganklikste roetes in die hospitaal.",
    lifespan=lifespan,
)

# Laat die webkoppelvlak toe om die API vanaf 'n ander oorsprong te bereik.
# Beperk allow_origins tot bekende adresse voordat die API ontplooi word.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def formateer_tyd(sekondes: float) -> str:
    """Formateer sekondes as byvoorbeeld 45s, 1m 17s of 2h 3m 4s."""
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
    """Formateer meter as byvoorbeeld 45m of 1.2km."""
    meter = max(0.0, meter)
    if meter >= 1000:
        return f"{meter / 1000:.1f}km"
    return f"{round(meter)}m"


@contextmanager
def db_verbinding():
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
    with db_verbinding() as conn:
        ry = conn.execute(
            """
            SELECT ai.kode_id, nk.naam, ai.beskrywing, ai.geaktiveer_op
            FROM aktiewe_insident ai
            JOIN noodkodes nk ON nk.kode_id = ai.kode_id
            WHERE ai.insident_id = 1
            """
        ).fetchone()
        if ry is None:
            return {"active": False, "blocked_node_ids": []}
        nodes = conn.execute(
            "SELECT node_id FROM insident_nodes WHERE insident_id = 1 ORDER BY node_id"
        ).fetchall()
    return {
        "active": True,
        "code": ry["kode_id"],
        "name": ry["naam"],
        "description": ry["beskrywing"] or "",
        "activated_at": ry["geaktiveer_op"],
        "blocked_node_ids": [node["node_id"] for node in nodes],
    }


def skep_sessie() -> str:
    inhoud = json.dumps(
        {"sub": ADMIN_GEBRUIKERSNAAM, "exp": int(time.time()) + SESSIE_SEKONDES},
        separators=(",", ":"),
    ).encode()
    data = base64.urlsafe_b64encode(inhoud).decode().rstrip("=")
    handtekening = hmac.new(SESSIE_GEHEIM.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{handtekening}"


def vereis_admin(hospitaal_admin_sessie: str | None = Cookie(default=None)) -> str:
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


@app.get("/")
def tuisblad():
    return {"boodskap": "Welkom by die Hospitaal Navigasie API. Gaan na /docs vir die dokumentasie."}


@app.get("/ui")
def ui():
    """Bedien die webkoppelvlak direk vanaf dieselfde API-adres."""
    html_pad = BASE_GIDS / "hospitaal_wayfinder.html"
    if not html_pad.exists():
        raise HTTPException(status_code=404, detail="hospitaal_wayfinder.html nie gevind nie.")
    return FileResponse(str(html_pad))


@app.get("/admin")
def admin_ui():
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
    """Bedien die webkoppelvlak se aparte stylblad."""
    css_pad = BASE_GIDS / "hospitaal_wayfinder.css"
    if not css_pad.exists():
        raise HTTPException(status_code=404, detail="hospitaal_wayfinder.css nie gevind nie.")
    return FileResponse(str(css_pad), media_type="text/css")


@app.get("/hospitaal_wayfinder.js", include_in_schema=False)
def ui_javascript():
    """Bedien die webkoppelvlak se aparte JavaScript."""
    js_pad = BASE_GIDS / "hospitaal_wayfinder.js"
    if not js_pad.exists():
        raise HTTPException(status_code=404, detail="hospitaal_wayfinder.js nie gevind nie.")
    return FileResponse(str(js_pad), media_type="text/javascript")


@app.get("/destinations")
def soek_bestemmings(
    q: str = Query("", description="Naam, node-ID, tipe, gebou of vloer"),
    limiet: int = Query(20, ge=1, le=100),
):
    """Vind mensleesbare bestemmings sonder dat die gebruiker node-ID's hoef te ken."""
    return {
        "soekterm": q,
        "bestemmings": app.state.grafiek.soek_bestemmings(q, limiet),
    }


@app.get("/incident")
def lees_insident():
    """Gee die huidige sluiting vir die openbare wayfinder terug."""
    return kry_insident()


@app.post("/admin/login")
def admin_login(invoer: AdminAanmelding, response: Response):
    gebruiker_ok = hmac.compare_digest(invoer.gebruikersnaam, ADMIN_GEBRUIKERSNAAM)
    wagwoord_ok = hmac.compare_digest(invoer.wagwoord, ADMIN_WAGWOORD)
    if not (gebruiker_ok and wagwoord_ok):
        raise HTTPException(status_code=401, detail="Verkeerde gebruikersnaam of wagwoord.")
    response.set_cookie(
        SESSIE_KOEKIE,
        skep_sessie(),
        max_age=SESSIE_SEKONDES,
        httponly=True,
        samesite="strict",
        secure=False,
    )
    return {"message": "Aanmelding suksesvol."}


@app.post("/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie(SESSIE_KOEKIE)
    return {"message": "Afgemeld."}


@app.get("/admin/map")
def admin_kaart(_: str = Depends(vereis_admin)):
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
                    """SELECT node_id, etiket, tipe_kode FROM nodes
                       WHERE vloer_id = ? ORDER BY etiket""",
                    (vloer["vloer_id"],),
                ).fetchall()
                vloer_data.append({**dict(vloer), "nodes": [dict(n) for n in nodes]})
            resultaat.append({**dict(gebou), "vloere": vloer_data})
        kodes = [dict(ry) for ry in conn.execute(
            "SELECT kode_id, naam FROM noodkodes ORDER BY naam"
        ).fetchall()]
    return {"geboue": resultaat, "noodkodes": kodes, "incident": kry_insident()}


@app.post("/admin/incident")
def aktiveer_insident(invoer: InsidentInvoer, _: str = Depends(vereis_admin)):
    node_ids = list(dict.fromkeys(invoer.node_ids))
    with db_verbinding() as conn:
        kode = conn.execute(
            "SELECT 1 FROM noodkodes WHERE kode_id = ?", (invoer.kode_id,)
        ).fetchone()
        if kode is None:
            raise HTTPException(status_code=400, detail="Ongeldige noodkode.")
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
        conn.execute("DELETE FROM aktiewe_insident")
        conn.execute(
            "INSERT INTO aktiewe_insident (insident_id, kode_id, beskrywing) VALUES (1, ?, ?)",
            (invoer.kode_id, invoer.beskrywing.strip()),
        )
        conn.executemany(
            "INSERT INTO insident_nodes (insident_id, node_id) VALUES (1, ?)",
            [(node_id,) for node_id in node_ids],
        )
    return kry_insident()


@app.delete("/admin/incident")
def kanselleer_insident(_: str = Depends(vereis_admin)):
    with db_verbinding() as conn:
        conn.execute("DELETE FROM aktiewe_insident")
    return {"active": False, "blocked_node_ids": []}


@app.get("/route")
def kry_roete(
    begin: str = Query(..., description="Die beginnodusse ID (bv. MAIN-G-ENT)"),
    doel: str = Query(..., description="Die eindnodusse ID (bv. SYGEBOU-1-RAD)"),
    gebruiker_tipe: str = Query("PUBLIEK", description="Gebruikerstipe (bv. PUBLIEK, PERSONEEL, NOODGEVAL)")
):
    """Bereken die vinnigste toegelate roete vir die gebruikerstipe."""
    try:
        insident = kry_insident()
        geblokkeer = set(insident["blocked_node_ids"])
        if begin in geblokkeer:
            raise HTTPException(status_code=409, detail="Die beginpunt is binne die geslote gebied.")
        if doel in geblokkeer:
            raise HTTPException(status_code=409, detail="Die bestemming is tydelik gesluit.")
        resultaat = app.state.grafiek.astar(
            begin, doel, gebruiker_tipe=gebruiker_tipe,
            geblokkeerde_nodes=geblokkeer,
        )

        if resultaat is None:
            raise HTTPException(
                status_code=409 if insident["active"] else 403,
                detail="Geen beskikbare roete om die huidige sluiting nie." if insident["active"] else "Geen roete gevind nie. Die pad bestaan nie of jy het nie toegang tot sekere nodusse nie."
            )

        pad, tyd_sekondes, afstand_m = resultaat
        return {
            "begin_node": begin,
            "doel_node": doel,
            "gebruiker_tipe": gebruiker_tipe,
            "geskatte_tyd_sekondes": round(tyd_sekondes, 1),
            "geskatte_tyd": formateer_tyd(tyd_sekondes),
            "geskatte_afstand_m": round(afstand_m, 1),
            "geskatte_afstand": formateer_afstand(afstand_m),
            "node_telling": len(pad),
            "pad": pad,
            "incident_active": insident["active"],
            "incident_code": insident.get("code"),
            "avoided_nodes": insident["blocked_node_ids"],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/route/image")
def kry_roete_prentjie(
    begin: str = Query(..., description="Die beginnodus se ID (bv. MAIN-G-ENT)"),
    doel: str = Query(..., description="Die eindnodus se ID (bv. SYGEBOU-1-RAD)"),
    gebruiker_tipe: str = Query(
        "PUBLIEK", description="Gebruikerstipe (bv. PUBLIEK, PERSONEEL, NOODGEVAL)"
    ),
):
    """Gee 'n PNG-vloerplan terug waarop die berekende roete uitgelig is."""
    try:
        insident = kry_insident()
        resultaat = app.state.grafiek.astar(
            begin, doel, gebruiker_tipe=gebruiker_tipe,
            geblokkeerde_nodes=set(insident["blocked_node_ids"]),
        )
        if resultaat is None:
            raise HTTPException(status_code=403, detail="Geen roete gevind nie.")

        pad, _, _ = resultaat
        tydelike_leer = tempfile.NamedTemporaryFile(
            prefix="hospitaal_roete_", suffix=".png", delete=False
        )
        uit_pad = Path(tydelike_leer.name)
        tydelike_leer.close()

        # Die tydelike lêer word ná die HTTP-antwoord deur BackgroundTask verwyder.
        teken_vloer_plan(str(DB_PAD), str(uit_pad), verlig_pad=pad)
        return FileResponse(
            uit_pad,
            media_type="image/png",
            filename="hospitaal_roete.png",
            background=BackgroundTask(uit_pad.unlink, missing_ok=True),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
