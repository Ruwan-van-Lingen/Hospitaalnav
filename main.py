# main.py
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from HospitaalGrafiek import HospitaalGrafiek, bou_demo_db
from starlette.background import BackgroundTask
from VloerPlan import teken_vloer_plan

BASE_GIDS = Path(__file__).resolve().parent
DB_PAD = BASE_GIDS / "hospitaal.db"
SKEMA_PAD = BASE_GIDS / "Skema.sql"
SEED_PAD = BASE_GIDS / "SeedData.sql"
AUTO_HERBOU_DB = os.getenv("AUTO_HERBOU_DB", "true").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Berei die databasis en grafiek voor voordat die API versoeke ontvang."""
    # Herbou die databasis by elke begin tydens ontwikkeling.
    # AUTO_HERBOU_DB=false om bestaande data in 'n produksie-omgewing te behou.
    if AUTO_HERBOU_DB:
        bou_demo_db(str(DB_PAD), str(SKEMA_PAD), str(SEED_PAD))

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


@app.get("/route")
def kry_roete(
    begin: str = Query(..., description="Die beginnodusse ID (bv. MAIN-G-ENT)"),
    doel: str = Query(..., description="Die eindnodusse ID (bv. SYGEBOU-1-RAD)"),
    gebruiker_tipe: str = Query("PUBLIEK", description="Gebruikerstipe (bv. PUBLIEK, PERSONEEL, NOODGEVAL)")
):
    """Bereken die vinnigste toegelate roete vir die gebruikerstipe."""
    try:
        resultaat = app.state.grafiek.astar(begin, doel, gebruiker_tipe=gebruiker_tipe)

        if resultaat is None:
            raise HTTPException(
                status_code=403,
                detail="Geen roete gevind nie. Die pad bestaan nie of jy het nie toegang tot sekere nodusse nie."
            )

        pad, tyd_sekondes = resultaat
        return {
            "begin_node": begin,
            "doel_node": doel,
            "gebruiker_tipe": gebruiker_tipe,
            "geskatte_tyd_sekondes": round(tyd_sekondes, 1),
            "geskatte_tyd": formateer_tyd(tyd_sekondes),
            "node_telling": len(pad),
            "pad": pad
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
        resultaat = app.state.grafiek.astar(
            begin, doel, gebruiker_tipe=gebruiker_tipe
        )
        if resultaat is None:
            raise HTTPException(status_code=403, detail="Geen roete gevind nie.")

        pad, _ = resultaat
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
