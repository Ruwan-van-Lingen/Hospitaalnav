from fastapi.testclient import TestClient

from main import app


def test_soek_bestemming_volgens_naam():
    with TestClient(app) as client:
        response = client.get("/destinations", params={"q": "Radiologie"})

    assert response.status_code == 200
    bestemmings = response.json()["bestemmings"]
    assert any(item["node_id"] == "ANNEX-1-RAD" for item in bestemmings)


def test_soek_bestemming_is_kas_onsensitief():
    with TestClient(app) as client:
        response = client.get("/destinations", params={"q": "icu"})

    assert response.status_code == 200
    assert response.json()["bestemmings"][0]["node_id"] == "MAIN-2-ICU"


def test_gevonde_node_werk_in_roete():
    with TestClient(app) as client:
        soek = client.get("/destinations", params={"q": "Radiologie"}).json()
        doel = soek["bestemmings"][0]["node_id"]
        response = client.get(
            "/route",
            params={
                "begin": "MAIN-G-ENT",
                "doel": doel,
                "gebruiker_tipe": "PUBLIEK",
            },
        )

    assert response.status_code == 200
    assert response.json()["pad"][-1] == "ANNEX-1-RAD"
