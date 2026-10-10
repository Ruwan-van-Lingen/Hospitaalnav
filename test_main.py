"""Geoutomatiseerde toetse vir die hospitaalnavigasie-API.

Voer uit met:
    python -m pytest -q

FastAPI se TestClient bedien die toepassing binne die toetsproses.
conftest.py verskaf 'n afsonderlike tydelike databasis per toets.
Die toetse dek formatering, bestemmingsoektog, toegang, roeteberekening,
PNG-uitvoer, administrasiesessies, sluitings en ontruiming.
"""

import sqlite3
from contextlib import closing

from fastapi.testclient import TestClient

import main
from HospitaalGrafiek import (
    BEREKEN_AFSTAND,
    BEREKEN_GEWIG,
    HospitaalGrafiek,
    bou_demo_db,
)
from main import app, formateer_tyd


# ---------------------------------------------------------------------------
# Eenheidtoetse — geen HTTP-versoeke nodig nie
# ---------------------------------------------------------------------------

def test_tydformaat():
    """Kontroleer dat sekondes as mensleesbare teks geformateer word."""
    assert formateer_tyd(45)   == "45s"
    assert formateer_tyd(77)   == "1m 17s"
    assert formateer_tyd(7384) == "2h 3m 4s"


def test_lambda_afstand_en_gewig():
    """Die lambda-funksies moet afstand en totale reistyd korrek bereken."""
    assert BEREKEN_AFSTAND((0, 0), (3, 4)) == 5.0
    assert BEREKEN_GEWIG(8, 25) == 33.0
    assert BEREKEN_GEWIG(15, 0) == 15.0


# ---------------------------------------------------------------------------
# Bestemmingsoektog
# ---------------------------------------------------------------------------

def test_soek_bestemming_volgens_naam():
    """Radiologie moet gevind word en SYGEBOU-1-RAD moet in die resultate wees."""
    with TestClient(app) as client:
        response = client.get("/destinations", params={"q": "Radiologie"})

    assert response.status_code == 200
    bestemmings = response.json()["bestemmings"]
    assert any(item["node_id"] == "SYGEBOU-1-RAD" for item in bestemmings)


def test_soek_bestemming_is_kas_onsensitief():
    """Soektog na 'icu' (kleinletters) moet MAIN-2-ICU terugstuur."""
    with TestClient(app) as client:
        response = client.get("/destinations", params={"q": "icu"})

    assert response.status_code == 200
    assert response.json()["bestemmings"][0]["node_id"] == "MAIN-2-ICU"


def test_nooddienste_is_beskikbaar_as_beginpunt():
    """Nooddienste moet as MAIN-G-ER gevind kan word."""
    with TestClient(app) as client:
        response = client.get("/destinations", params={"q": "Nooddienste"})

    assert response.status_code == 200
    assert response.json()["bestemmings"][0]["node_id"] == "MAIN-G-ER"


def test_fisioterapie_het_volledige_metadata_en_werk_as_bestemming():
    """Die nuwe Fisioterapie-nodus moet soekbaar en roeteerbaar wees."""
    with TestClient(app) as client:
        soektog = client.get("/destinations", params={"q": "Fisioterapie"})
        roete = client.get(
            "/route",
            params={
                "begin": "MAIN-G-ENT",
                "doel": "SYGEBOU-G-PHY",
                "gebruiker_tipe": "PUBLIEK",
            },
        )

    assert soektog.status_code == 200
    assert soektog.json()["bestemmings"] == [
        {
            "node_id": "SYGEBOU-G-PHY",
            "etiket": "Fisioterapie",
            "tipe_kode": "DEPARTEMENT",
            "beperkte_groep": None,
            "vloer_id": "SYGEBOU-G",
            "vloer_naam": "Grondvloer",
            "gebou_id": "SYGEBOU",
            "gebou_naam": "Sygebou",
        }
    ]
    assert roete.status_code == 200
    assert roete.json()["pad"][-1] == "SYGEBOU-G-PHY"


def test_ou_aanhoudende_databasis_kry_ontbrekende_seed_data(monkeypatch):
    """AUTO_HERBOU_DB=false moet ontbrekende SQL-nodusse veilig byvoeg."""
    bou_demo_db(str(main.DB_PAD), str(main.SKEMA_PAD), str(main.SEED_PAD))
    with closing(sqlite3.connect(main.DB_PAD)) as conn:
        conn.execute(
            "DELETE FROM rande WHERE van_node = ? OR na_node = ?",
            ("SYGEBOU-G-PHY", "SYGEBOU-G-PHY"),
        )
        conn.execute("DELETE FROM nodes WHERE node_id = ?", ("SYGEBOU-G-PHY",))
        conn.commit()

    monkeypatch.setattr(main, "AUTO_HERBOU_DB", False)
    with TestClient(app) as client:
        soektog = client.get("/destinations", params={"q": "Fisioterapie"})
        roete = client.get(
            "/route",
            params={
                "begin": "MAIN-G-ENT",
                "doel": "SYGEBOU-G-PHY",
                "gebruiker_tipe": "PUBLIEK",
            },
        )

    assert soektog.status_code == 200
    assert soektog.json()["bestemmings"][0]["node_id"] == "SYGEBOU-G-PHY"
    assert roete.status_code == 200


# ---------------------------------------------------------------------------
# Kaartdata vir die webkoppelvlak
# ---------------------------------------------------------------------------

def test_kaart_kom_uit_die_databasis():
    """/kaart moet presies dieselfde nodusse en rande as die grafiek bevat."""
    with TestClient(app) as client:
        antwoord = client.get("/kaart")
        grafiek = app.state.grafiek

    assert antwoord.status_code == 200
    kaart = antwoord.json()
    assert {n["node_id"] for n in kaart["nodes"]} == set(grafiek.nodes)
    # Elke rand verbind twee nodusse wat op die kaart bestaan.
    node_ids = {n["node_id"] for n in kaart["nodes"]}
    assert all(r["van_node"] in node_ids and r["na_node"] in node_ids for r in kaart["rande"])
    # Vloere kom per gebou van onder na bo, soos die webkoppelvlak se oortjies.
    assert [v["vloer_id"] for v in kaart["vloere"]] == [
        "MAIN-G", "MAIN-1", "MAIN-2", "SYGEBOU-G", "SYGEBOU-1",
    ]
    assert [g["gebou_id"] for g in kaart["geboue"]] == ["MAIN", "SYGEBOU"]
    # Die nodus waarvan die JS-kopie ooit verskil het: die databasis is die waarheid.
    ry = next(n for n in kaart["nodes"] if n["node_id"] == "MAIN-1-J01")
    assert ry["tipe_kode"] == "DEPARTEMENT"


def test_ou_databasis_kry_noodkodes_en_kolomme_terug(monkeypatch):
    """
    'n Databasis van voor die noodkodes (geen kodes, geen vooraf-tabel, geen
    outomaties_modus-kolom) moet by opstart volledig opgegradeer word:
    verseker_insident_skema() herstel die struktuur en SeedData.sql die kodes.
    """
    bou_demo_db(str(main.DB_PAD), str(main.SKEMA_PAD), str(main.SEED_PAD))
    with closing(sqlite3.connect(main.DB_PAD)) as conn:
        conn.execute("DROP TABLE noodkode_vooraf_nodes")
        conn.execute("DELETE FROM noodkodes")
        conn.execute("ALTER TABLE noodkodes DROP COLUMN outomaties_modus")
        conn.commit()

    monkeypatch.setattr(main, "AUTO_HERBOU_DB", False)
    with TestClient(app) as client:
        client.post("/admin/login", json={"gebruikersnaam": "admin", "wagwoord": "admin"})
        kaart = client.get("/admin/map").json()

    kodes = {k["kode_id"]: k for k in kaart["noodkodes"]}
    assert set(kodes) == {"ONDERHOUD", "SKOONMAAK", "ROOI", "PINK"}
    assert kodes["ROOI"]["outomaties_modus"] == "ONTRUIM_ALMAL"
    assert kodes["PINK"]["outomaties_modus"] == "SLUIT_ALLES"
    assert "MAIN-G-ELV" in kodes["ONDERHOUD"]["vooraf_node_ids"]
    assert "MAIN-2-OR" in kodes["SKOONMAAK"]["vooraf_node_ids"]


# ---------------------------------------------------------------------------
# Roeteberekening
# ---------------------------------------------------------------------------

def test_gevonde_node_werk_in_roete():
    """
    Volledige integrasietoets: soek 'n bestemming en gebruik dan die nodus-ID
    in 'n roeteversoek. Kontroleer die pad, tyd en afstand.
    """
    with TestClient(app) as client:
        soek = client.get("/destinations", params={"q": "Radiologie"}).json()
        doel = soek["bestemmings"][0]["node_id"]
        response = client.get(
            "/route",
            params={"begin": "MAIN-G-ENT", "doel": doel, "gebruiker_tipe": "PUBLIEK"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["pad"][-1] == "SYGEBOU-1-RAD"
    assert data["geskatte_tyd"] == "1m 23s"
    assert data["geskatte_afstand_m"] == 83.0
    assert data["geskatte_afstand"] == "83m"


def test_personeel_kan_icu_bereik():
    """Personeel moet toegang tot die beperkte intensiewesorgnodus hê."""
    with TestClient(app) as client:
        response = client.get(
            "/route",
            params={"begin": "MAIN-G-ENT", "doel": "MAIN-2-ICU", "gebruiker_tipe": "PERSONEEL"},
        )

    assert response.status_code == 200
    assert response.json()["pad"][-1] == "MAIN-2-ICU"


def test_ongeldige_gebruikerstipe_word_verwerp():
    """'n Onbekende gebruikerstipe moet 400 met 'n duidelike foutboodskap terugstuur."""
    with TestClient(app) as client:
        response = client.get(
            "/route",
            params={"begin": "MAIN-G-ENT", "doel": "SYGEBOU-1-RAD", "gebruiker_tipe": "ONBEKEND"},
        )

    assert response.status_code == 400
    assert "Ongeldige gebruikerstipe" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Bediening van die webkoppelvlak
# ---------------------------------------------------------------------------

def test_ui_word_bedien():
    """Die /ui-eindpunt moet HTML bedien; CSS en JS moet ook bereikbaar wees."""
    with TestClient(app) as client:
        response      = client.get("/ui")
        css_response  = client.get("/hospitaal_wayfinder.css")
        js_response   = client.get("/hospitaal_wayfinder.js")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert css_response.status_code == 200
    assert css_response.headers["content-type"].startswith("text/css")
    assert js_response.status_code == 200
    assert js_response.headers["content-type"].startswith("text/javascript")


def test_roeteprent_is_png():
    """Die /route/image-eindpunt moet 'n geldige PNG-lêer lewer."""
    with TestClient(app) as client:
        response = client.get(
            "/route/image",
            params={"begin": "MAIN-G-ENT", "doel": "SYGEBOU-1-RAD", "gebruiker_tipe": "PUBLIEK"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    # Kontroleer die PNG-handtekening in die eerste 8 grepe.
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


# ---------------------------------------------------------------------------
# Adminaanmelding en sessiebeskerming
# ---------------------------------------------------------------------------

def test_admin_eindpunte_vereis_aanmelding():
    """Beskermde eindpunte moet 401 terugstuur sonder 'n geldige sessiekoekie."""
    with TestClient(app) as client:
        response = client.get("/admin/map")
        blad     = client.get("/admin")

    assert response.status_code == 401
    # Die administrasieblad is publiek; die administrasie-API vereis aanmelding.
    assert blad.status_code == 200
    assert "Sluitingsadministrasie" in blad.text


def test_admin_kan_sluiting_aktiveer_en_kanselleer():
    """
    Volledige sluitingslewensiklus:
      1. Aanmelding → 2. Aktiveer sluiting → 3. Bevestig via /incident → 4. Kanselleer.
    """
    with TestClient(app) as client:
        login = client.post(
            "/admin/login",
            json={"gebruikersnaam": "admin", "wagwoord": "admin"},
        )
        assert login.status_code == 200

        aktiveer = client.post(
            "/admin/incident",
            json={"kode_id": "ONDERHOUD", "beskrywing": "Toetssluiting", "node_ids": ["MAIN-1-BRIDGE"]},
        )
        assert aktiveer.status_code == 200
        assert aktiveer.json()["blocked_node_ids"] == ["MAIN-1-BRIDGE"]

        # Die openbare /incident-eindpunt moet die aktiewe sluiting bevestig.
        openbaar = client.get("/incident")
        assert openbaar.json()["active"] is True

        kanselleer = client.delete("/admin/incident")
        assert kanselleer.status_code == 200
        assert client.get("/incident").json()["active"] is False


# ---------------------------------------------------------------------------
# Sluiting en A*-ompad
# ---------------------------------------------------------------------------

def test_astar_roeteer_om_aktiewe_sluiting(admin_client):
    """
    A* moet 'n alternatiewe roete vind wanneer die lugbrug (MAIN-1-BRIDGE)
    geblokkeer is. Die alternatiewe pad deur die tonnel neem langer.
    """
    # Die normale roete gebruik die lugbrug.
    normaal = admin_client.get(
        "/route",
        params={"begin": "MAIN-G-ENT", "doel": "SYGEBOU-1-RAD"},
    ).json()
    assert "MAIN-1-BRIDGE" in normaal["pad"]

    # Blokkeer die lugbrug.
    admin_client.post(
        "/admin/incident",
        json={"kode_id": "ONDERHOUD", "node_ids": ["MAIN-1-BRIDGE"]},
    )
    ompad = admin_client.get(
        "/route",
        params={"begin": "MAIN-G-ENT", "doel": "SYGEBOU-1-RAD"},
    )

    assert ompad.status_code == 200
    assert ompad.json()["incident_active"] is True
    assert "MAIN-1-BRIDGE" not in ompad.json()["pad"]
    # Die alternatiewe pad moet meer tyd as die direkte lugbrugpad verg.
    assert ompad.json()["geskatte_tyd_sekondes"] > normaal["geskatte_tyd_sekondes"]


# ---------------------------------------------------------------------------
# Ontruimingsmodus
# ---------------------------------------------------------------------------

def test_ontruimingsroete_vind_naaste_uitgang():
    """
    Ontruimingsmodus moet 'n pad na 'n nooduitgang vind, ongeag die
    gebruiker se gewenste bestemming.
    """
    with TestClient(app) as client:
        response = client.get(
            "/route/ontruim",
            params={"begin": "MAIN-2-ICU", "gebruiker_tipe": "PERSONEEL"},
        )
    assert response.status_code == 200
    data = response.json()
    uitgang = data["uitgang_node"]
    # Slegs hierdie drie nodusse het is_nooduitgang=1 in SeedData.sql.
    assert uitgang in {"MAIN-G-ENT", "MAIN-G-AMB", "SYGEBOU-G-ENT"}
    assert data["pad"][0] == "MAIN-2-ICU"   # Pad begin by die beginpunt.
    assert data["pad"][-1] == uitgang        # Pad eindig by die nooduitgang.


def test_ontruimingsroete_verbied_hysbakke(tmp_path):
    """
    Geen hysbakrand (rand_tipe='HUISBAK') mag in die ontruimingspad voorkom nie.
    Dit verifieer die uitsluiting direk in die roete-algoritme.
    """
    db_pad = tmp_path / "ontruiming.db"
    bou_demo_db(str(db_pad), str(main.SKEMA_PAD), str(main.SEED_PAD))
    grafiek = HospitaalGrafiek(str(db_pad))
    resultaat = grafiek.naaste_veilige_uitgang("MAIN-2-ICU", gebruiker_tipe="PERSONEEL")
    assert resultaat is not None, "Moet 'n ontruimingsroete vind."
    pad, _, _ = resultaat

    with closing(sqlite3.connect(db_pad)) as verbinding:
        hysbak_rande = {
            (row[0], row[1])
            for row in verbinding.execute(
                "SELECT van_node, na_node FROM rande WHERE rand_tipe='HUISBAK'"
            )
        }

    # Kontroleer elke opeenvolgende paar in albei moontlike randrigtings.
    for a, b in zip(pad, pad[1:]):
        assert (a, b) not in hysbak_rande and (b, a) not in hysbak_rande, (
            f"Ontruimingspad gebruik 'n hysbakrand: {a} → {b}"
        )


def test_ontruimingsmodus_insident_aktiveer_en_roeteer(admin_client):
    """
    Aktiveer 'n insident met ontruimings_modus=True en bevestig dat:
      • Die API die vlag korrek stoor en terugstuur.
      • Die openbare /incident-eindpunt die vlag weerspieël.
      • /route/ontruim steeds werk terwyl die insident aktief is.
    """
    aktiveer = admin_client.post(
        "/admin/incident",
        json={
            "kode_id": "SKOONMAAK",
            "beskrywing": "Gevaarlike materiaal gevind",
            "node_ids": ["MAIN-1-BRIDGE"],
            "ontruimings_modus": True,
        },
    )
    assert aktiveer.status_code == 200
    assert aktiveer.json()["ontruimings_modus"] is True

    openbaar = admin_client.get("/incident")
    assert openbaar.json()["ontruimings_modus"] is True

    ontruim = admin_client.get("/route/ontruim", params={"begin": "MAIN-G-ENT"})
    assert ontruim.status_code == 200


def test_ontruimingsroete_geen_veilige_uitgang(admin_client):
    """
    As alle nooduitgange (MAIN-G-ENT, MAIN-G-AMB, SYGEBOU-G-ENT) geblokkeer is,
    moet /route/ontruim 409 terugstuur.
    """
    admin_client.post(
        "/admin/incident",
        json={
            "kode_id": "ONDERHOUD",
            "node_ids": ["MAIN-G-ENT", "MAIN-G-AMB", "SYGEBOU-G-ENT"],
            "ontruimings_modus": True,
        },
    )
    response = admin_client.get("/route/ontruim", params={"begin": "MAIN-1-WARDA"})
    assert response.status_code == 409


def test_geslote_bestemming_gee_konflik(admin_client):
    """
    As die teikennodus self geblokkeer is, moet /route 409 terugstuur
    met 'n verduideliking dat die bestemming tydelik gesluit is.
    """
    admin_client.post(
        "/admin/incident",
        json={"kode_id": "SKOONMAAK", "node_ids": ["SYGEBOU-1-RAD"]},
    )
    response = admin_client.get(
        "/route",
        params={"begin": "MAIN-G-ENT", "doel": "SYGEBOU-1-RAD"},
    )
    assert response.status_code == 409
    assert "tydelik gesluit" in response.json()["detail"]


def test_gewone_en_ontruimingsroete_deel_dieselfde_antwoordvelde():
    """
    Beide roete-eindpunte bou hul antwoord met bou_roete_antwoord(), so hulle
    moet dieselfde velde hê; net die ontruimingsantwoord het uitgang_node.
    """
    with TestClient(app) as client:
        gewoon = client.get("/route", params={"begin": "MAIN-G-ENT", "doel": "SYGEBOU-1-RAD"}).json()
        ontruim = client.get("/route/ontruim", params={"begin": "MAIN-1-WARDA"}).json()

    assert set(ontruim) - set(gewoon) == {"uitgang_node"}
    assert set(gewoon) <= set(ontruim)
    assert gewoon["ontruimings_modus"] is False
    assert "uitgang_node" not in gewoon
    assert ontruim["ontruimings_modus"] is True
    assert ontruim["doel_node"] == ontruim["uitgang_node"] == ontruim["pad"][-1]


# ---------------------------------------------------------------------------
# Outomatiese noodkodes (Kode Rooi / Kode Pink)
# ---------------------------------------------------------------------------

def test_kode_rooi_ontruim_almal_sonder_nodus_keuse(admin_client):
    """
    Kode Rooi (ROOI, outomaties_modus='ONTRUIM_ALMAL') moet ontruimingsmodus
    aktiveer sonder dat enige node_ids verskaf word, en geen nodusse moet
    geblokkeer wees nie (die brand se presiese ligging word nie gemodelleer
    nie — almal word bloot na die naaste uitgang gestuur).
    """
    aktiveer = admin_client.post("/admin/incident", json={"kode_id": "ROOI", "node_ids": []})
    assert aktiveer.status_code == 200
    data = aktiveer.json()
    assert data["ontruimings_modus"] is True
    assert data["blocked_node_ids"] == []
    assert data["outomaties_modus"] == "ONTRUIM_ALMAL"

    # Die personeellid moet steeds 'n ontruimingsroete vanaf intensiewe sorg kry.
    ontruim = admin_client.get("/route/ontruim", params={"begin": "MAIN-2-ICU", "gebruiker_tipe": "PERSONEEL"})
    assert ontruim.status_code == 200


def test_kode_rooi_ignoreer_kliënt_nodus_keuse(admin_client):
    """
    Selfs as die kliënt (per ongeluk of moedswillig) node_ids saam met Kode
    Rooi stuur, moet die bediener dit ignoreer — die outomatiese gedrag is
    altyd bedienerkant afgedwing.
    """
    aktiveer = admin_client.post(
        "/admin/incident",
        json={"kode_id": "ROOI", "node_ids": ["MAIN-1-BRIDGE"], "ontruimings_modus": False},
    )
    assert aktiveer.status_code == 200
    data = aktiveer.json()
    assert data["blocked_node_ids"] == []
    assert data["ontruimings_modus"] is True


def test_kode_pink_sluit_die_hele_hospitaal(admin_client):
    """
    Kode Pink (PINK, outomaties_modus='SLUIT_ALLES') moet ELKE nodus in die
    databasis outomaties blokkeer. Daarna moet /route vir enige paar
    beginpunt/bestemming misluk (409, want die beginpunt self is geblokkeer).
    """
    aktiveer = admin_client.post("/admin/incident", json={"kode_id": "PINK", "node_ids": []})
    assert aktiveer.status_code == 200
    data = aktiveer.json()
    assert data["ontruimings_modus"] is False
    assert data["outomaties_modus"] == "SLUIT_ALLES"
    assert len(data["blocked_node_ids"]) > 20  # elke nodus in SeedData.sql

    geblokkeer = admin_client.get(
        "/route", params={"begin": "MAIN-G-ENT", "doel": "SYGEBOU-1-RAD"}
    )
    assert geblokkeer.status_code == 409


def test_gewone_noodkode_vereis_steeds_minstens_een_nodus(admin_client):
    """
    'n Handmatige (nie-outomatiese) noodkode moet steeds die bestaande
    reël afdwing: minstens een nodus moet gekies word.
    """
    response = admin_client.post("/admin/incident", json={"kode_id": "ONDERHOUD", "node_ids": []})
    assert response.status_code == 400
    assert "minstens een nodus" in response.json()["detail"]


def test_admin_map_bevat_outomaties_modus_per_kode(admin_client):
    """Noodkodemetadata moet outomaties_modus vir die administrasieblad insluit."""
    kaart = admin_client.get("/admin/map").json()
    kodes = {k["kode_id"]: k["outomaties_modus"] for k in kaart["noodkodes"]}
    assert kodes["ROOI"] == "ONTRUIM_ALMAL"
    assert kodes["PINK"] == "SLUIT_ALLES"
    assert kodes["ONDERHOUD"] is None


def test_admin_map_bevat_voorafkeuses_en_slegs_aktiewe_insidenttipes(admin_client):
    """Die administrasiekeuselys moet tipes en hul voorafgekose nodusse ontvang."""
    kaart = admin_client.get("/admin/map").json()

    kodes = {kode["kode_id"]: kode for kode in kaart["noodkodes"]}
    assert set(kodes) == {"ONDERHOUD", "SKOONMAAK", "ROOI", "PINK"}
    assert set(kodes["ONDERHOUD"]["vooraf_node_ids"]) == {
    "MAIN-G-ELV",
    "MAIN-1-ELV",
    "MAIN-2-ELV",
    "SYGEBOU-G-ELV",
    "SYGEBOU-1-ELV",
    }
    assert set(kodes["SKOONMAAK"]["vooraf_node_ids"]) == {
    "MAIN-1-WARDA",
    "MAIN-1-WARDB",
    "MAIN-2-OR",
    }
    assert kodes["ROOI"]["vooraf_node_ids"] == []
    assert kodes["PINK"]["vooraf_node_ids"] == []
