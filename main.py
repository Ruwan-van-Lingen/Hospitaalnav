# main.py
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from HospitaalGrafiek import HospitaalGrafiek, bou_demo_db

app = FastAPI(
    title="Hospitaal Padvinder API",
    description="API vir die berekening van die kortste en toeganklikste roetes in die hospitaal."
)

# Laat toe dat die frontend (op 'n ander poort/origin) hierdie API kan bereik.
# Vir produksie: vervang allow_origins=["*"] met die spesifieke frontend-URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PAD = "hospitaal.db"
AUTO_HERBOU_DB = os.getenv("AUTO_HERBOU_DB", "true").lower() == "true"


@app.on_event("startup")
def startup_event():
    # Dev: herbou elke start. Prod: stel AUTO_HERBOU_DB=false
    if AUTO_HERBOU_DB:
        bou_demo_db(DB_PAD, "Skema.sql", "SeedData.sql")

    # Laai die grafiek eenmaal in geheue op
    app.state.grafiek = HospitaalGrafiek(DB_PAD)


@app.get("/")
def tuisblad():
    return {"boodskap": "Welkom by die Hospitaal Padvinder API. Gaan na /docs vir die dokumentasie."}


@app.get("/route")
def kry_roete(
    begin: str = Query(..., description="Die beginnodusse ID (bv. MAIN-G-ENT)"),
    doel: str = Query(..., description="Die eindnodusse ID (bv. ANNEX-1-RAD)"),
    gebruiker_tipe: str = Query("PUBLIEK", description="Gebruikerstipe (bv. PUBLIEK, STAFF, NOODGEVAL)")
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
