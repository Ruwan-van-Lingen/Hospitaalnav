"""Toetse vir die groot-datastel-vertoning (stap 1): data, roetes, ontruiming, Kruskal en vloei.

Voer uit met:
    python -m pytest test_groot.py -q
"""

import math
import random

import pytest

from groot_algoritmes import (
    GrootGrafiek, SORTEER_METODES, astar, bereken_ontruimingskaart,
    dijkstra, kruskal, maks_vloei_na_uitgange,
)
from groot_data import genereer_toetsdata, laai_csv, stoor_csv
from mst_en_vloei import bereken_min_spanboom


@pytest.fixture(scope="module")
def graf():
    """Een gedeelde, kleiner toetsgrafiek (400 nodusse, 4 vloere); dieselfde saad gee altyd dieselfde grafiek."""
    return genereer_toetsdata(400, 4, saad=3)


def klein_graf():
    """Handgebou grafiek met bekende antwoorde: A en B kan elk na die uitgang U, maar B se pad is duurder."""
    g = GrootGrafiek()
    for naam, x in (("A", 0), ("B", 10), ("M", 20), ("U", 30)):
        g.voeg_nodus_by(naam, naam, 0, x, 0, is_nooduitgang=(naam == "U"))
    g.voeg_rand_by("A", "M", "GANG", 20, 20, 3.0)
    g.voeg_rand_by("B", "M", "GANG", 10, 10, 2.0)
    g.voeg_rand_by("M", "U", "GANG", 10, 10, 4.0)
    return g


def test_generator_is_herhaalbaar_en_verbind(graf):
    """Dieselfde saad gee dieselfde grafiek; die spanboom het presies V-1 rande (dus verbind)."""
    weer = genereer_toetsdata(400, 4, saad=3)
    assert graf.rande_lys == weer.rande_lys
    assert len(graf.nodes) == 400
    uitslag = kruskal(graf.nodes, graf.ongerigte_kante())
    assert uitslag.aantal_komponente == 1
    assert len(uitslag.kante) == 399


def test_astar_en_dijkstra_vind_dieselfde_tyd_en_astar_brei_minder_uit(graf):
    """Albei is korrek (dieselfde minimum tyd); A* brei gemiddeld minder nodusse uit."""
    rng = random.Random(1)
    ids = list(graf.nodes)
    dijk_totaal = ster_totaal = 0
    for _ in range(30):
        a, b = rng.sample(ids, 2)
        d, s = dijkstra(graf, a, b), astar(graf, a, b)
        assert math.isclose(d.tyd_s, s.tyd_s, rel_tol=1e-9)
        assert d.pad[0] == s.pad[0] == a and d.pad[-1] == s.pad[-1] == b
        dijk_totaal += d.besoek_telling
        ster_totaal += s.besoek_telling
    assert ster_totaal < dijk_totaal


def test_geblokkeerde_nodus_word_omseil_of_gee_none():
    g = klein_graf()
    assert dijkstra(g, "A", "U").pad == ["A", "M", "U"]
    assert dijkstra(g, "A", "U", geblokkeer={"M"}) is None   # M is die enigste brug.
    assert dijkstra(g, "A", "U", geblokkeer={"A"}) is None
    with pytest.raises(ValueError):
        dijkstra(g, "A", "ONBEKEND")


def test_ontruimingskaart_klein_en_pad_eindig_by_uitgang():
    g = klein_graf()
    kaart = bereken_ontruimingskaart(g)
    assert kaart.tyd_s == {"U": 0.0, "M": 10.0, "A": 30.0, "B": 20.0}
    assert kaart.pad("A") == ["A", "M", "U"]
    assert bereken_ontruimingskaart(g, {"U"}).pad("A") is None   # Geen uitgang oor nie.


def test_ontruiming_pad_tyd_klop_en_gebruik_geen_hysbak(graf):
    """Vir elke nodus: die pad eindig by 'n uitgang, die randtye tel op tot die tyd, en geen rand is 'n hysbak."""
    kaart = bereken_ontruimingskaart(graf)
    assert len(kaart.tyd_s) == len(graf.nodes)
    for begin in graf.nodes:
        pad = kaart.pad(begin)
        assert graf.nodes[pad[-1]]["is_nooduitgang"]
        totaal = 0.0
        for a, b in zip(pad, pad[1:]):
            randte = [r for r in graf.adjacency[a] if r.na_node == b and r.rand_tipe != "HUISBAK"]
            assert randte, f"Geen toelaatbare rand {a} -> {b}"
            totaal += min(r.gewig_s for r in randte)
        assert totaal == pytest.approx(kaart.tyd_s[begin])


@pytest.mark.parametrize("metode", list(SORTEER_METODES))
def test_kruskal_alle_sorteermetodes_stem_ooreen_met_verwysing(graf, metode):
    """Elke sorteermetode gee dieselfde totale gewig as die bestaande Kruskal in mst_en_vloei.py."""
    kante = graf.ongerigte_kante()
    verwys_kante, verwys_gewig = bereken_min_spanboom(graf.nodes, kante)
    uitslag = kruskal(graf.nodes, kante, SORTEER_METODES[metode])
    assert uitslag.totale_gewig == pytest.approx(verwys_gewig)
    assert len(uitslag.kante) == len(verwys_kante)


def test_kruskal_ontkoppelde_grafiek_gee_spanwoud():
    g = klein_graf()
    g.voeg_nodus_by("X", "X", 0, 99, 99)   # Geen rande nie.
    uitslag = kruskal(g.nodes, g.ongerigte_kante())
    assert uitslag.aantal_komponente == 2


def test_maks_vloei_klein_netwerk_en_snit():
    """A en B stuur saam deur M -> U (kapasiteit 4): vloei 4, bottelnek is M -> U."""
    g = klein_graf()
    uitslag = maks_vloei_na_uitgange(g, ["A", "B"])
    assert uitslag.maks_vloei == 4.0
    assert uitslag.bottelnekke == [("M", "U", 4.0)]
    assert maks_vloei_na_uitgange(g, ["U"]) is None            # Bron is self die uitgang.
    assert maks_vloei_na_uitgange(g, ["A"], {"U"}) is None     # Geen uitgang oor.


def test_maks_vloei_snitkapasiteit_gelyk_aan_vloei_en_trappe_is_bottelnek(graf):
    """Max-flow = min-cut: die snit se kapasiteite tel op tot die vloei. Die boonste vloer ontruim deur trappe."""
    bo = max(d["vloer"] for d in graf.nodes.values())
    bronne = [n for n, d in graf.nodes.items() if d["vloer"] == bo]
    uitslag = maks_vloei_na_uitgange(graf, bronne)
    assert uitslag.maks_vloei > 0
    assert sum(k for _, _, k in uitslag.bottelnekke) == pytest.approx(uitslag.maks_vloei)
    # Hysbakke is uitgesluit, dus kan 'n bottelnek nooit 'n hysbakrand wees nie.
    tipes = {r.rand_tipe for van, na, _ in uitslag.bottelnekke
             for r in graf.adjacency[van] if r.na_node == na}
    assert "HUISBAK" not in tipes


def test_csv_heen_en_terug(graf, tmp_path):
    nodusse, rande = tmp_path / "nodusse.csv", tmp_path / "rande.csv"
    stoor_csv(graf, nodusse, rande)
    terug = laai_csv(nodusse, rande)
    assert terug.nodes == graf.nodes
    assert terug.rande_lys == graf.rande_lys


def test_csv_met_foute_gee_duidelike_boodskap(tmp_path):
    nodusse, rande = tmp_path / "n.csv", tmp_path / "r.csv"
    nodusse.write_text("node_id,etiket,vloer,pos_x,pos_y,tipe_kode,is_nooduitgang\nA,A,0,0,0,DEPARTEMENT,0\n", encoding="utf-8")
    rande.write_text("van_node,na_node,rand_tipe,afstand_m,gewig_s,kapasiteit,bidirectional\nA,A,GANG,x,1,,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Reël 2"):
        laai_csv(nodusse, rande)
    rande.write_text("van_node,na_node\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ontbreek"):
        laai_csv(nodusse, rande)


def test_kunsmatige_vloeipunte_bots_nie_met_nodusname_nie():
    graf = GrootGrafiek()
    for naam in ("__SUPER_BRON__", "__SUPER_PUT__", "U"):
        graf.voeg_nodus_by(naam, naam, 0, 0, 0, is_nooduitgang=naam == "U")
    graf.voeg_rand_by("__SUPER_BRON__", "__SUPER_PUT__", "GANG", 1, 1, 3)
    graf.voeg_rand_by("__SUPER_PUT__", "U", "GANG", 1, 1, 2)
    uit = maks_vloei_na_uitgange(graf, ["__SUPER_BRON__"])
    assert uit.maks_vloei == 2
    assert uit.bottelnekke == [("__SUPER_PUT__", "U", 2)]
