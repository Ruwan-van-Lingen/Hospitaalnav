from fastapi.testclient import TestClient

from main import app, formateer_tyd


def test_tydformaat():
    assert formateer_tyd(45) == "45s"
    assert formateer_tyd(77) == "1m 17s"
    assert formateer_tyd(7384) == "2h 3m 4s"


def test_soek_bestemming_volgens_naam():
    with TestClient(app) as client:
        response = client.get("/destinations", params={"q": "Radiologie"})

    assert response.status_code == 200
    bestemmings = response.json()["bestemmings"]
    assert any(item["node_id"] == "SYGEBOU-1-RAD" for item in bestemmings)


def test_soek_bestemming_is_kas_onsensitief():
    with TestClient(app) as client:
        response = client.get("/destinations", params={"q": "icu"})

    assert response.status_code == 200
    assert response.json()["bestemmings"][0]["node_id"] == "MAIN-2-ICU"


def test_nooddienste_is_beskikbaar_as_beginpunt():
    with TestClient(app) as client:
        response = client.get("/destinations", params={"q": "Nooddienste"})

    assert response.status_code == 200
    assert response.json()["bestemmings"][0]["node_id"] == "MAIN-G-ER"


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
    data = response.json()
    assert data["pad"][-1] == "SYGEBOU-1-RAD"
    assert data["geskatte_tyd"] == "1m 23s"
    assert data["geskatte_afstand_m"] == 83.0
    assert data["geskatte_afstand"] == "83m"


def test_personeel_kan_icu_bereik():
    with TestClient(app) as client:
        response = client.get(
            "/route",
            params={
                "begin": "MAIN-G-ENT",
                "doel": "MAIN-2-ICU",
                "gebruiker_tipe": "PERSONEEL",
            },
        )

    assert response.status_code == 200
    assert response.json()["pad"][-1] == "MAIN-2-ICU"


def test_ongeldige_gebruikerstipe_word_verwerp():
    with TestClient(app) as client:
        response = client.get(
            "/route",
            params={
                "begin": "MAIN-G-ENT",
                "doel": "SYGEBOU-1-RAD",
                "gebruiker_tipe": "ONBEKEND",
            },
        )

    assert response.status_code == 400
    assert "Ongeldige gebruikerstipe" in response.json()["detail"]


def test_ui_word_bedien():
    with TestClient(app) as client:
        response = client.get("/ui")

        css_response = client.get("/hospitaal_wayfinder.css")
        js_response = client.get("/hospitaal_wayfinder.js")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert css_response.status_code == 200
    assert css_response.headers["content-type"].startswith("text/css")
    assert js_response.status_code == 200
    assert js_response.headers["content-type"].startswith("text/javascript")


def test_roeteprent_is_png():
    with TestClient(app) as client:
        response = client.get(
            "/route/image",
            params={
                "begin": "MAIN-G-ENT",
                "doel": "SYGEBOU-1-RAD",
                "gebruiker_tipe": "PUBLIEK",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
