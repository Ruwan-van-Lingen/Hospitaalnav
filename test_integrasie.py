"""Regressietoetse vir geïntegreerde ontleding, sessies en ontruimingsreëls."""

import base64
import hashlib
import hmac
import json
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

import main
from HospitaalGrafiek import kontroleer_alle_nodusse_dekking


def meld_aan(client):
    """Gebruik die toetsbewyse wat conftest.py afsonderlik instel."""
    antwoord = client.post(
        "/admin/login", json={"gebruikersnaam": "admin", "wagwoord": "admin"}
    )
    assert antwoord.status_code == 200


@pytest.mark.parametrize("eindpunt", [
    "/analise/spanboom", "/analise/maks_vloei?bron=MAIN-G-ER", "/admin/dekking-kontrole",
])
def test_ontleding_vereis_admin(eindpunt):
    with TestClient(main.app) as client:
        assert client.get(eindpunt).status_code == 401
        assert main.app.state.dekking_pool is None


def test_spanboom_en_maksimumvloei():
    with TestClient(main.app) as client:
        meld_aan(client)
        antwoord = client.get("/analise/spanboom")
        assert antwoord.status_code == 200
        boom = antwoord.json()
        assert boom["is_verbind"] is True
        assert boom["aantal_komponente"] == 1
        assert boom["aantal_kante"] == len(main.app.state.grafiek.nodes) - 1
        assert sum(rand["gewig_s"] for rand in boom["kante"]) == pytest.approx(boom["totale_gewig_s"])

        vloei = client.get("/analise/maks_vloei", params={"bron": "MAIN-G-ER"})
        assert vloei.status_code == 200
        data = vloei.json()
        assert data["maks_vloei_persone_per_s"] > 0
        assert data["reeds_by_uitgang"] is False
        assert sum(rand["kapasiteit"] for rand in data["bottelnek_kante"]) == pytest.approx(
            data["maks_vloei_persone_per_s"]
        )
        uitgang = client.get("/analise/maks_vloei", params={"bron": "MAIN-G-ENT"}).json()
        assert uitgang["reeds_by_uitgang"] is True
        assert uitgang["maks_vloei_persone_per_s"] == 0
        assert uitgang["bottelnek_kante"] == []

        assert client.post("/admin/incident", json={"kode_id": "PINK"}).status_code == 200
        assert client.get("/analise/maks_vloei", params={"bron": "MAIN-G-ER"}).status_code == 409


@pytest.mark.parametrize("eindpunt,parameters", [
    ("/analise/maks_vloei", {"bron": "ONBEKEND"}),
    ("/analise/maks_vloei", {"bron": "MAIN-G-ER", "gebruiker_tipe": "ONBEKEND"}),
    ("/admin/dekking-kontrole", {"gebruiker_tipe": "ONBEKEND"}),
])
def test_ontleding_verwerp_ongeldige_invoer(eindpunt, parameters):
    with TestClient(main.app) as client:
        meld_aan(client)
        assert client.get(eindpunt, params=parameters).status_code == 400
        assert main.app.state.dekking_pool is None


def test_parallelle_dekking_stem_ooreen_en_poel_word_hergebruik():
    """Gebruik werklike werkprosesse, ook ná 'n insidentverandering."""
    with TestClient(main.app) as client:
        assert main.app.state.dekking_pool is None
        meld_aan(client)
        poel = None
        for kode, geblokkeer in [(None, set()), ("ONDERHOUD", {"MAIN-1-BRIDGE"}), ("PINK", None)]:
            if kode:
                assert client.post("/admin/incident", json={
                    "kode_id": kode, "node_ids": sorted(geblokkeer or set()),
                }).status_code == 200
            gesluit = set(main.kry_insident()["blocked_node_ids"])
            verwag = kontroleer_alle_nodusse_dekking(main.app.state.grafiek, "PUBLIEK", gesluit)
            antwoord = client.get("/admin/dekking-kontrole")
            assert antwoord.status_code == 200
            data = antwoord.json()
            assert data["alle_resultate"] == verwag
            assert data["totaal_nodusse"] == len(verwag)
            assert data["onbereikbaar"] == [r for r in verwag if not r["bereikbaar"]]
            assert data["onbereikbaar_telling"] == len(data["onbereikbaar"])
            if poel is None:
                poel = main.app.state.dekking_pool
            assert main.app.state.dekking_pool is poel
        assert poel is not None
        assert poel._mp_context.get_start_method() == "spawn"
    assert main.app.state.dekking_pool is None


def test_kode_rooi_dwing_json_en_prent_na_uitgang(monkeypatch):
    """Selfs 'n gewone /route-versoek mag die noodmodus nie omseil nie."""
    getekende_paaie = []
    oorspronklike_teken = main.teken_vloer_plan

    def teken(db_pad, uit_pad, verlig_pad):
        getekende_paaie.append(verlig_pad)
        return oorspronklike_teken(db_pad, uit_pad, verlig_pad=verlig_pad)

    monkeypatch.setattr(main, "teken_vloer_plan", teken)
    with TestClient(main.app) as client:
        meld_aan(client)
        assert client.post("/admin/incident", json={"kode_id": "ROOI"}).status_code == 200
        parameters = {"begin": "MAIN-1-WARDA", "doel": "SYGEBOU-1-RAD"}
        antwoord = client.get("/route", params=parameters)
        assert antwoord.status_code == 200
        roete = antwoord.json()
        assert roete["ontruimings_modus"] is True
        assert roete["doel_node"] == roete["uitgang_node"] == roete["pad"][-1]
        assert main.app.state.grafiek.nodes[roete["uitgang_node"]]["is_nooduitgang"]
        assert roete["incident_code"] == "ROOI"
        prent = client.get("/route/image", params=parameters)
        assert prent.status_code == 200
        assert prent.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert getekende_paaie == [roete["pad"]]


def test_prent_roete_respekteer_sluiting():
    with TestClient(main.app) as client:
        meld_aan(client)
        assert client.post("/admin/incident", json={"kode_id": "PINK"}).status_code == 200
        antwoord = client.get("/route/image", params={"begin": "MAIN-G-ENT", "doel": "SYGEBOU-1-RAD"})
        assert antwoord.status_code == 409


def test_tekenfout_laat_geen_tydelike_prent_agter(tmp_path, monkeypatch):
    oorspronklike_tydelik = tempfile.NamedTemporaryFile

    def tydelike_leer(**kwargs):
        return oorspronklike_tydelik(dir=tmp_path, **kwargs)

    def foutiewe_teken(*args, **kwargs):
        raise RuntimeError("Doelbewuste tekenfout")

    monkeypatch.setattr(main.tempfile, "NamedTemporaryFile", tydelike_leer)
    monkeypatch.setattr(main, "teken_vloer_plan", foutiewe_teken)
    with TestClient(main.app) as client:
        with pytest.raises(RuntimeError, match="Doelbewuste tekenfout"):
            client.get("/route/image", params={"begin": "MAIN-G-ENT", "doel": "SYGEBOU-1-RAD"})
    assert list(tmp_path.glob("hospitaal_roete_*.png")) == []


def test_unicode_aanmeldbewyse_word_korrek_hanteer(monkeypatch):
    with TestClient(main.app) as client:
        assert client.post("/admin/login", json={"gebruikersnaam": "Jân", "wagwoord": "geheimë"}).status_code == 401
        monkeypatch.setattr(main, "ADMIN_GEBRUIKERSNAAM", "Jân")
        monkeypatch.setattr(main, "ADMIN_WAGWOORD", "geheimë")
        assert client.post("/admin/login", json={"gebruikersnaam": "Jân", "wagwoord": "geheimë"}).status_code == 200
        assert client.get("/admin/map").status_code == 200
        assert client.post("/admin/logout").status_code == 200
        assert client.get("/admin/map").status_code == 401


@pytest.mark.parametrize("inhoud", [
    [], None, {"sub": "admin"}, {"sub": "admin", "exp": "later"},
    {"sub": "admin", "exp": float("nan")}, {"sub": "admin", "exp": float("inf")},
    {"sub": "admin", "exp": 0}, {"sub": "verkeerd", "exp": 9999999999},
])
def test_ongeldige_sessie_inhoud_word_verwerp(inhoud):
    """Selfs ondertekende maar misvormde inhoud mag nooit 500 veroorsaak nie."""
    data = base64.urlsafe_b64encode(json.dumps(inhoud).encode()).decode().rstrip("=")
    handtekening = hmac.new(main.SESSIE_GEHEIM.encode(), data.encode(), hashlib.sha256).hexdigest()
    with TestClient(main.app) as client:
        client.cookies.set(main.SESSIE_KOEKIE, f"{data}.{handtekening}")
        assert client.get("/admin/map").status_code == 401


def test_sessie_verval_presies_op_vervaltydstip(monkeypatch):
    with TestClient(main.app) as client:
        meld_aan(client)
        verval = int(time.time()) + main.SESSIE_SEKONDES
        monkeypatch.setattr(main.time, "time", lambda: verval)
        assert client.get("/admin/map").status_code == 401
