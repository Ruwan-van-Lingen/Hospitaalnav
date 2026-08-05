import tempfile
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from HospitaalGrafiek import HospitalGraph, build_demo_db
from VloerPlan import draw_floor_plan
from pathlib import Path
from starlette.background import BackgroundTask

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "hospital.db"
SCHEMA_PATH = BASE_DIR / "Schema.sql"
SEED_PATH = BASE_DIR / "SeedData.sql"

app = FastAPI(
    title="Hospitaal Padvinder API",
    description="API vir die berekening van die kortste en toeganklikste roetes in die hospitaal.",
)

# Bou die databasis by opstart as dit nog nie bestaan nie.
if not DB_PATH.exists():
    build_demo_db(str(DB_PATH), str(SCHEMA_PATH), str(SEED_PATH))

# Laai die grafiek eenmaal in geheue op
graph = HospitalGraph(str(DB_PATH))


@app.get("/")
def tuisblad():
    return {
        "boodskap": "Welkom by die Hospitaal Padvinder API. Gaan na /docs vir die dokumentasie."
    }



@app.get("/route")
def kry_roete(
    start: str = Query(..., description="Die beginnodusse ID (bv. MAIN-G-ENT)"),
    goal: str = Query(..., description="Die eindnodusse ID (bv. ANNEX-1-RAD)"),
    user_type: str = Query(
        "PUBLIC", description="Gebruikerstipe (bv. PUBLIC, STAFF, EMERGENCY)"
    ),
):
    """
    Bereken die vinnigste roete tussen twee punte gebaseer op die gebruikerstipe.
    """
    try:
        result = graph.astar(start, goal, user_type=user_type)

        if result is None:
            raise HTTPException(
                status_code=403,
                detail="Geen roete gevind nie. Die pad bestaan nie of jy het nie toegang tot sekere nodusse nie.",
            )

        path, time_seconds = result
        return {
            "start_node": start,
            "goal_node": goal,
            "user_type": user_type,
            "estimated_time_seconds": round(time_seconds, 1),
            "node_count": len(path),
            "path": path,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/route/image")
def kry_roete_prentjie(
    start: str = Query(..., description="Start node ID (bv. MAIN-G-ENT)"),
    goal: str = Query(..., description="Goal node ID (bv. ANNEX-1-RAD)"),
    user_type: str = Query("PUBLIC", description="Gebruikerstipe (bv. PUBLIC, STAFF)"),
):
    """
    Bereken die roete en gee 'n PNG-afbeelding van die vloerplan terug met die pad uitgelig.
    """
    try:
        result = graph.astar(start, goal, user_type=user_type)

        if result is None:
            raise HTTPException(status_code=403, detail="Geen pad gevind nie.")

        path, _ = result
        temp_file = tempfile.NamedTemporaryFile(
            prefix="hospitaal_roete_", suffix=".png", delete=False
        )
        output_path = Path(temp_file.name)
        temp_file.close()

        # Genereer die afbeelding
        draw_floor_plan(str(DB_PATH), str(output_path), highlight_path=path)

        # Stuur die afbeelding terug na gebruiker se webblaaier
        return FileResponse(
            output_path,
            media_type="image/png",
            filename="hospitaal_roete.png",
            background=BackgroundTask(output_path.unlink, missing_ok=True),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
