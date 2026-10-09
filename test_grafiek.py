"""Onafhanklike verwysingstoetse en grensgevalle vir die grafiekalgoritmes."""

import copy
import heapq
import math
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest

import HospitaalGrafiek as grafiek_module
from HospitaalGrafiek import HospitaalGrafiek, Rand, VERSTEK_KAPASITEIT, bou_demo_db


@pytest.fixture
def voorbeeld_db(tmp_path):
    """Skep slegs 'n tydelike databasis uit die projek se voorbeelddata."""
    gids = Path(__file__).parent
    db_pad = tmp_path / "grafiek.db"
    bou_demo_db(str(db_pad), str(gids / "Skema.sql"), str(gids / "SeedData.sql"))
    return db_pad


@pytest.fixture
def voorbeeld_grafiek(voorbeeld_db):
    """Laai 'n HospitaalGrafiek uit die tydelike voorbeelddatabasis."""
    return HospitaalGrafiek(str(voorbeeld_db))


def bou_klein_grafiek(nodusse, kante, uitgange=(), beperkings=None):
    """Bou 'n gerigte toetsgrafiek; elke kant bevat bron, doel, tyd, kapasiteit en tipe."""
    grafiek = HospitaalGrafiek.__new__(HospitaalGrafiek)
    beperkings = beperkings or {}
    grafiek.nodes = {
        naam: {
            "pos": (float(i * 10), float(i % 2)),
            "level": 0,
            "beperkte_groep": beperkings.get(naam),
            "is_nooduitgang": naam in uitgange,
        }
        for i, naam in enumerate(nodusse)
    }
    grafiek.adjacency = {naam: [] for naam in nodusse}
    for van, na, tyd, kapasiteit, tipe in kante:
        grafiek.adjacency[van].append(Rand(na, tyd, tipe, 0, tyd * 2, kapasiteit))
    grafiek.toegelate_groepe = lambda tipe: (
        {"SLEGS_PERSONEEL", "SLEGS_ICU"} if tipe == "PERSONEEL" else set()
    )
    grafiek._skaal_heuristiek()
    return grafiek


def dijkstra_verwysing(grafiek, begin, toegelaat, geblokkeer, ontruim=False):
    """Bereken reistye onafhanklik van A*, die heuristiek en roeteherstel."""
    bruikbaar = {
        n for n, data in grafiek.nodes.items()
        if n not in geblokkeer
        and (data["beperkte_groep"] is None or data["beperkte_groep"] in toegelaat)
    }
    if begin not in bruikbaar:
        return {}
    afstande = {begin: 0.0}
    hoop = [(0.0, begin)]
    while hoop:
        tyd, huidige = heapq.heappop(hoop)
        if tyd > afstande[huidige]:
            continue
        for rand in grafiek.adjacency[huidige]:
            if rand.na_node not in bruikbaar or (ontruim and rand.rand_tipe == "HUISBAK"):
                continue
            nuwe_tyd = tyd + rand.gewig_s
            if nuwe_tyd < afstande.get(rand.na_node, math.inf):
                afstande[rand.na_node] = nuwe_tyd
                heapq.heappush(hoop, (nuwe_tyd, rand.na_node))
    return afstande


@pytest.mark.parametrize("gebruiker", ["PUBLIEK", "PERSONEEL", "PASIENT_VERVOER", "NOODGEVAL"])
@pytest.mark.parametrize("geblokkeer", [set(), {"MAIN-G-J01", "MAIN-1-STA", "MAIN-G-AMB"}])
def test_astar_alle_noduspare_stem_ooreen_met_dijkstra(voorbeeld_grafiek, gebruiker, geblokkeer):
    """Kontroleer alle 26 × 26 pare vir elke toegangstipe en sluitingscenario."""
    grafiek = voorbeeld_grafiek
    groepe = grafiek.toegelate_groepe(gebruiker)
    for begin in grafiek.nodes:
        verwag = dijkstra_verwysing(grafiek, begin, groepe, geblokkeer)
        for doel in grafiek.nodes:
            resultaat = grafiek.astar(begin, doel, gebruiker, geblokkeer)
            if doel not in verwag:
                assert resultaat is None, (gebruiker, begin, doel)
                continue
            assert resultaat is not None, (gebruiker, begin, doel)
            pad, tyd, afstand = resultaat
            assert tyd == pytest.approx(verwag[doel]), (gebruiker, begin, doel)
            assert pad[0] == begin and pad[-1] == doel
            assert not set(pad) & geblokkeer
            rande = [
                min((r for r in grafiek.adjacency[a] if r.na_node == b), key=lambda r: r.gewig_s)
                for a, b in zip(pad, pad[1:])
            ]
            assert tyd == pytest.approx(sum(r.gewig_s for r in rande))
            assert afstand == pytest.approx(sum(r.afstand_m for r in rande))


def test_heuristiek_is_konsekwent_vir_elke_rand_en_doel(voorbeeld_grafiek):
    """Konsekwentheid: h(van) is hoogstens randkoste + h(na), en h(doel) is 0. Dit hou A* korrek."""
    grafiek = voorbeeld_grafiek
    for doel in grafiek.nodes:
        assert grafiek._heuristic(doel, doel) == 0
        for van, rande in grafiek.adjacency.items():
            for rand in rande:
                h_van = grafiek._heuristic(van, doel)
                assert 0 <= h_van <= rand.gewig_s + grafiek._heuristic(rand.na_node, doel) + 1e-10


def test_astar_kostelose_rand_en_misleidende_koordinate():
    """Met 'n kostelose rand en koördinate wat die heuristiek mislei, vind A* steeds die goedkoopste pad."""
    grafiek = bou_klein_grafiek("ABC", [
        ("A", "C", 10, 1, "GANG"),
        ("A", "B", 0, 1, "GANG"),
        ("B", "C", 1, 1, "GANG"),
    ])
    grafiek.nodes["B"]["pos"] = (10000.0, 10000.0)
    grafiek._skaal_heuristiek()
    assert grafiek.astar("A", "C") == (["A", "B", "C"], 1.0, 2.0)


@pytest.mark.parametrize("gebruiker", ["PUBLIEK", "PERSONEEL", "PASIENT_VERVOER", "NOODGEVAL"])
def test_ontruiming_stem_ooreen_met_voorwaartse_dijkstra(voorbeeld_grafiek, gebruiker):
    """Die omgekeerde multibron-Dijkstra gee dieselfde minimum tyd as 'n gewone Dijkstra vanaf elke beginpunt."""
    grafiek = voorbeeld_grafiek
    geblokkeer = {"MAIN-G-ENT", "MAIN-1-STA"}
    groepe = grafiek.toegelate_groepe(gebruiker)
    for begin in grafiek.nodes:
        afstande = dijkstra_verwysing(grafiek, begin, groepe, geblokkeer, ontruim=True)
        uitgange = [tyd for n, tyd in afstande.items() if grafiek.nodes[n]["is_nooduitgang"]]
        resultaat = grafiek.naaste_veilige_uitgang(begin, gebruiker, geblokkeer)
        if not uitgange:
            assert resultaat is None
        else:
            assert resultaat is not None
            assert resultaat[1] == pytest.approx(min(uitgange))
            assert grafiek.nodes[resultaat[0][-1]]["is_nooduitgang"]


def test_ontruiming_behou_eenrigting_en_parallelle_rande():
    """Ontruiming volg slegs werklike randrigtings en kies die goedkoopste van parallelle rande."""
    grafiek = bou_klein_grafiek("ABU", [
        ("A", "U", 9, 1, "GANG"),
        ("A", "U", 2, 1, "GANG"),
        ("U", "B", 1, 1, "GANG"),
    ], uitgange={"U"})
    assert grafiek.naaste_veilige_uitgang("A") == (["A", "U"], 2.0, 4.0)
    assert grafiek.naaste_veilige_uitgang("B") is None
    assert grafiek.naaste_veilige_uitgang("U") == (["U"], 0.0, 0.0)


def test_ontruiming_geen_hysbak_of_geblokkeerde_uitgang():
    """Hysbakke word by ontruiming uitgesluit, en 'n geblokkeerde uitgang of beginpunt gee None."""
    grafiek = bou_klein_grafiek("AU", [("A", "U", 1, 5, "HUISBAK")], uitgange={"U"})
    assert grafiek.astar("A", "U") is not None
    assert grafiek.naaste_veilige_uitgang("A") is None
    grafiek.adjacency["A"][0].rand_tipe = "TRAPPE"
    assert grafiek.naaste_veilige_uitgang("A", geblokkeerde_nodes={"U"}) is None
    assert grafiek.naaste_veilige_uitgang("A", geblokkeerde_nodes={"A"}) is None


def test_mst_kies_goedkoopste_parallelle_en_omgekeerde_rand():
    """Kruskal behandel die grafiek as ongerig en gebruik die goedkoopste rand per noduspaar; 'n afgesnyde nodus gee 'n spanwoud."""
    grafiek = bou_klein_grafiek("ABCD", [
        ("A", "B", 20, 1, "GANG"),
        ("A", "B", 6, 1, "GANG"),
        ("B", "A", 2, 1, "GANG"),
        ("B", "C", 3, 1, "GANG"),
        ("A", "C", 9, 1, "GANG"),
        ("C", "C", 0, 1, "GANG"),
    ])
    # D is afgesny: die resultaat is 'n minimum spanwoud, sonder selflusse.
    kante, totaal = grafiek.bereken_min_spanboom()
    assert totaal == 5
    assert {(frozenset((a, b)), w) for a, b, w in kante} == {
        (frozenset(("A", "B")), 2), (frozenset(("B", "C")), 3),
    }
    assert bou_klein_grafiek([], []).bereken_min_spanboom() == ([], 0.0)


def test_maks_vloei_bekende_netwerk_minimumsnit_en_geen_mutasie():
    """'n Klein netwerk met 'n bekende antwoord (vloei 5, min-snit by die bron); die grafiek word nie verander nie."""
    grafiek = bou_klein_grafiek("SABU", [
        ("S", "A", 1, 3, "GANG"),
        ("S", "B", 1, 2, "GANG"),
        ("A", "B", 1, 1, "GANG"),
        ("A", "U", 1, 2, "GANG"),
        ("B", "U", 1, 3, "GANG"),
    ], uitgange={"U"})
    voor = copy.deepcopy(grafiek.adjacency)
    verwag = (5.0, [("S", "A", 3), ("S", "B", 2)])
    assert grafiek.maks_vloei_na_uitgange("S") == verwag
    assert grafiek.maks_vloei_na_uitgange("S") == verwag
    assert grafiek.adjacency == voor


def test_maks_vloei_sluit_hysbakke_en_ontoeganklike_snitrande_uit():
    """Hysbakke, geblokkeerde nodusse en beperkte areas bly buite die vloeinetwerk."""
    grafiek = bou_klein_grafiek("SABXHU", [
        ("S", "A", 1, 5, "GANG"),
        ("A", "U", 1, 2, "GANG"),
        ("S", "B", 1, 7, "GANG"),
        ("B", "U", 1, 7, "GANG"),
        ("S", "X", 1, 11, "GANG"),
        ("X", "U", 1, 11, "GANG"),
        ("S", "H", 1, 100, "HUISBAK"),
        ("H", "U", 1, 100, "GANG"),
    ], uitgange={"U"}, beperkings={"X": "SLEGS_PERSONEEL"})
    assert grafiek.maks_vloei_na_uitgange("S", geblokkeerde_nodes={"B"}) == (
        2.0, [("A", "U", 2)],
    )
    assert grafiek.maks_vloei_na_uitgange("S", "PERSONEEL", {"B"})[0] == 13


def test_maks_vloei_meer_uitgange_parallelle_rande_en_teenrigtings():
    """Meer as een uitgang, parallelle rande en teenrigtingrande tel korrek saam; die snit se kapasiteit is gelyk aan die vloei."""
    grafiek = bou_klein_grafiek(["S", "A", "U", "__SUPERPUT__"], [
        ("S", "A", 1, 2, "GANG"),
        ("S", "A", 1, 3, "GANG"),
        ("A", "S", 1, 9, "GANG"),
        ("A", "U", 1, 3, "GANG"),
        ("A", "__SUPERPUT__", 1, 2, "GANG"),
    ], uitgange={"U", "__SUPERPUT__"})
    vloei, snit = grafiek.maks_vloei_na_uitgange("S")
    assert vloei == 5
    assert sum(kapasiteit for _, _, kapasiteit in snit) == vloei


def test_maks_vloei_grensgevalle():
    """Geen uitgang, bron is self die uitgang, geblokkeerde bron en onbekende bron."""
    grafiek = bou_klein_grafiek("SAU", [("S", "A", 1, 1, "GANG")], uitgange={"U"})
    assert grafiek.maks_vloei_na_uitgange("S") is None
    assert grafiek.maks_vloei_na_uitgange("U") == (0.0, [])
    assert grafiek.maks_vloei_na_uitgange("U", geblokkeerde_nodes={"U"}) is None
    assert grafiek.maks_vloei_na_uitgange("S", geblokkeerde_nodes={"S"}) is None
    grafiek.nodes["U"]["is_nooduitgang"] = False
    assert grafiek.maks_vloei_na_uitgange("S") is None
    with pytest.raises(ValueError):
        grafiek.maks_vloei_na_uitgange("ONGELDIG")


@pytest.mark.parametrize("veld", ["gewig_s", "afstand_m", "kapasiteit"])
@pytest.mark.parametrize("waarde", [-1.0, math.inf, -math.inf, math.nan])
def test_rand_verwerp_negatiewe_en_nie_eindige_waardes(veld, waarde):
    """Rand weier negatiewe, oneindige en NaN-waardes."""
    waardes = dict(na_node="U", gewig_s=1, rand_tipe="GANG", vloer_verander=0, afstand_m=1, kapasiteit=1)
    waardes[veld] = waarde
    with pytest.raises(ValueError):
        Rand(**waardes)


def test_rand_laat_nulwaardes_toe():
    """Nul is 'n geldige gewig, afstand en kapasiteit."""
    assert Rand("U", 0, "GANG", 0, 0, 0).kapasiteit == 0


def test_laaier_lees_kapasiteit_en_verstek(voorbeeld_db):
    """Die kapasiteit-kolom word gelees; NULL val terug op VERSTEK_KAPASITEIT."""
    with sqlite3.connect(voorbeeld_db) as conn:
        if "kapasiteit" not in {ry[1] for ry in conn.execute("PRAGMA table_info(rande)")}:
            conn.execute("ALTER TABLE rande ADD COLUMN kapasiteit REAL")
        conn.execute("UPDATE rande SET kapasiteit = NULL")
        conn.execute("UPDATE rande SET kapasiteit = 2.75 WHERE van_node = 'MAIN-G-ENT'")
    grafiek = HospitaalGrafiek(str(voorbeeld_db))
    assert grafiek.adjacency["MAIN-G-ENT"][0].kapasiteit == 2.75
    assert any(r.kapasiteit == 2.75 for r in grafiek.adjacency["MAIN-G-J01"] if r.na_node == "MAIN-G-ENT")
    assert all(r.kapasiteit == VERSTEK_KAPASITEIT for r in grafiek.adjacency["MAIN-1-STA"])


def test_laaier_aanvaar_ouer_skema_sonder_kapasiteit(voorbeeld_db):
    """'n Ouer databasis sonder die kapasiteit-kolom laai steeds, met die verstek."""
    with sqlite3.connect(voorbeeld_db) as conn:
        if "kapasiteit" in {ry[1] for ry in conn.execute("PRAGMA table_info(rande)")}:
            conn.execute("ALTER TABLE rande DROP COLUMN kapasiteit")
    grafiek = HospitaalGrafiek(str(voorbeeld_db))
    assert all(r.kapasiteit == VERSTEK_KAPASITEIT for rande in grafiek.adjacency.values() for r in rande)


def test_lambda_funksies_word_deur_laaier_en_roetes_gebruik(voorbeeld_db, monkeypatch):
    """Spioene bewys dat die laaier en A* werklik die twee lambda-funksies aanroep."""
    afstand = grafiek_module.BEREKEN_AFSTAND
    gewig = grafiek_module.BEREKEN_GEWIG
    assert afstand.__name__ == gewig.__name__ == "<lambda>"
    assert afstand((0, 0), (3, 4)) == 5
    assert gewig(8, 25) == 33
    afstand_spioen = Mock(wraps=afstand)
    gewig_spioen = Mock(wraps=gewig)
    monkeypatch.setattr(grafiek_module, "BEREKEN_AFSTAND", afstand_spioen)
    monkeypatch.setattr(grafiek_module, "BEREKEN_GEWIG", gewig_spioen)
    grafiek = HospitaalGrafiek(str(voorbeeld_db))
    assert gewig_spioen.call_count > 0
    vorige_telling = afstand_spioen.call_count
    assert grafiek.astar("MAIN-G-ENT", "SYGEBOU-1-RAD") is not None
    assert afstand_spioen.call_count > vorige_telling
    assert any(r.gewig_s == 33 for r in grafiek.adjacency["MAIN-G-ELV"] if r.rand_tipe == "HUISBAK")


def test_toegelate_groepe_kom_uit_geheue_en_gee_kopie(voorbeeld_grafiek, monkeypatch):
    """Toegangsregte word by laai gelees; daarna raak toegelate_groepe() nie die databasis nie."""
    def geen_databasis(*args, **kwargs):
        raise AssertionError("toegelate_groepe() mag nie weer die databasis oopmaak nie.")

    monkeypatch.setattr(grafiek_module.sqlite3, "connect", geen_databasis)
    assert voorbeeld_grafiek.toegelate_groepe("PUBLIEK") == set()
    assert voorbeeld_grafiek.toegelate_groepe("PERSONEEL") == {"SLEGS_PERSONEEL", "SLEGS_ICU"}
    assert voorbeeld_grafiek.toegelate_groepe("PASIENT_VERVOER") == {"SLEGS_PERSONEEL"}

    # 'n Verandering aan die teruggegewe stel mag die gestoorde regte nie raak nie.
    stel = voorbeeld_grafiek.toegelate_groepe("PUBLIEK")
    stel.add("SLEGS_ICU")
    assert voorbeeld_grafiek.toegelate_groepe("PUBLIEK") == set()

    with pytest.raises(ValueError, match="Ongeldige gebruikerstipe"):
        voorbeeld_grafiek.toegelate_groepe("ONBEKEND")
