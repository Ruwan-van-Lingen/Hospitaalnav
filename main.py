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
    # Dev: herbou elke start. Prod: stel AUTO_HERBOU_DB=false
    if AUTO_HERBOU_DB:
        bou_demo_db(str(DB_PAD), str(SKEMA_PAD), str(SEED_PAD))

    # Laai die grafiek eenmaal in geheue op
    app.state.grafiek = HospitaalGrafiek(str(DB_PAD))
    yield


app = FastAPI(
    title="Hospitaal Padvinder API",
    description="API vir die berekening van die kortste en toeganklikste roetes in die hospitaal.",
    lifespan=lifespan,
)

# Laat toe dat die frontend (op 'n ander poort/origin) hierdie API kan bereik.
# Vir produksie: vervang allow_origins=["*"] met die spesifieke frontend-URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def tuisblad():
    return {"boodskap": "Welkom by die Hospitaal Padvinder API. Gaan na /docs vir die dokumentasie."}


@app.get("/ui")             #die is sodat die correcte api laai vir die link 
def ui():
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
    doel: str = Query(..., description="Die eindnodusse ID (bv. ANNEX-1-RAD)"),
    gebruiker_tipe: str = Query("PUBLIEK", description="Gebruikerstipe (bv. PUBLIEK, PERSONEEL, NOODGEVAL)")
):
    """
    Bereken die vinnigste roete tussen twee punte gebaseer op die gebruikerstipe.
    """
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
            "node_telling": len(pad),
            "pad": pad
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/route/image")
def kry_roete_prentjie(
    begin: str = Query(..., description="Die beginnodus se ID (bv. MAIN-G-ENT)"),
    doel: str = Query(..., description="Die eindnodus se ID (bv. ANNEX-1-RAD)"),
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

        teken_vloer_plan(str(DB_PAD), str(uit_pad), verlig_pad=pad)
        return FileResponse(
            uit_pad,
            media_type="image/png",
            filename="hospitaal_roete.png",
            background=BackgroundTask(uit_pad.unlink, missing_ok=True),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
