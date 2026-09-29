"""Kontroleer bestemmingsoektog deur die 2-4-boom en herlaai van metadata."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import main


@pytest.mark.parametrize(
    "term",
    ["  DIologie  ", "SYGEBOU-1-RAD", "DEPARTEMENT", "Sygebou", "Vlak 1 - Radiologie"],
)
def test_metadata_api_gebruik_boom_sonder_nuwe_sql(monkeypatch, term):
    """Naam- en metadatatreffers kom uit die boom sonder verdere SQL-navrae."""
    with TestClient(main.app) as client:
        assert main.app.state.grafiek.bestemmingsindeks.valideer()

        def geen_sql(*args, **kwargs):
            raise AssertionError("Die metadata-soektog moet die boom gebruik.")

        with monkeypatch.context() as tydelik:
            tydelik.setattr(sqlite3, "connect", geen_sql)
            response = client.get("/destinations", params={"q": term, "limiet": 100})
        assert response.status_code == 200
        item = next(item for item in response.json()["bestemmings"] if item["node_id"] == "SYGEBOU-1-RAD")
        assert item["node_id"] == "SYGEBOU-1-RAD"
        assert {"etiket", "node_id", "vloer_id", "vloer_naam", "gebou_id", "gebou_naam", "tipe_kode", "beperkte_groep"} == set(item)
        roete = client.get("/route", params={"begin": "MAIN-G-ENT", "doel": item["node_id"]})
        assert roete.status_code == 200


def test_een_soektog_limiete_en_letterlike_teks():
    """Bevestig die soekvolgorde, letterlike teks en die API se limietvalidering."""
    with TestClient(main.app) as client:
        assert client.get("/destinations", params={"q": "diologie"}).json()["bestemmings"]
        assert client.get("/destinations", params={"q": "bestaan-nie"}).json()["bestemmings"] == []
        assert client.get("/destinations", params={"q": "%"}).json()["bestemmings"] == []
        items = client.get("/destinations", params={"limiet": 3}).json()["bestemmings"]
        assert len(items) == 3
        assert items == sorted(items, key=lambda item: (item["etiket"].strip().casefold(), item["node_id"]))
        assert client.get("/destinations", params={"limiet": 0}).status_code == 422
        assert 'id="soekModus"' not in client.get("/ui").text
        parameters = client.get("/openapi.json").json()["paths"]["/destinations"]["get"]["parameters"]
        assert {p["name"] for p in parameters} == {"q", "limiet"}


def test_herbou_na_naamverandering_en_beskerm_metadata():
    """Resultaatkopieë beskerm die indeks; herbou lees nuwe databasisname."""
    with TestClient(main.app):
        grafiek = main.app.state.grafiek
        item = grafiek.soek_bestemmings("diologie")[0]
        item["etiket"] = "Verander deur leser"
        assert grafiek.soek_bestemmings("diologie")[0]["etiket"] == "Radiologie"
        conn = sqlite3.connect(main.DB_PAD)
        try:
            conn.execute("UPDATE nodes SET etiket = ? WHERE node_id = ?", ("X-straal", "SYGEBOU-1-RAD"))
            conn.commit()
        finally:
            conn.close()
        grafiek.herbou_bestemmingsindeks()
        # Die vloer se naam bevat steeds Radiologie; die ou nodusetiket is weg.
        assert all(
            bestemming["etiket"] != "Radiologie"
            for bestemming in grafiek.soek_bestemmings("diologie")
        )
        assert grafiek.soek_bestemmings("straal")[0]["node_id"] == "SYGEBOU-1-RAD"
        assert grafiek.bestemmingsindeks.valideer()
