import os
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from HospitaalGrafiek import HospitalGraph, build_demo_db
from VloerPlan import draw_floor_plan
from pathlib import Path

app = FastAPI(
    title="Hospitaal Padvinder API",
    description="API vir die berekening van die kortste en toeganklikste roetes in die hospitaal.",
)

# Bou/hernu die databasis by opstart as dit nog nie bestaan nie
build_demo_db("hospital.db", "Schema.sql", "seedData.sql")

# Laai die grafiek eenmaal in geheue op
graph = HospitalGraph("hospital.db")


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
    background_tasks: BackgroundTasks,
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
        output_filename = "temp_roete.png"

        # Genereer die afbeelding
        draw_floor_plan("hospital.db", output_filename, highlight_path=path)

        # Skeduleer om die tydelike prentjie uit te vee ná die versoek voltooi is
        if os.path.exists(output_filename):
            background_tasks.add_task(os.remove, output_filename)

        # Stuur die afbeelding terug na gebruiker se webblaaier
        return FileResponse(
            output_filename,
            media_type="image/png",
            background=BackgroundTasks(
                lambda: Path(output_filename).unlink(missing_ok=True)
            ),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
