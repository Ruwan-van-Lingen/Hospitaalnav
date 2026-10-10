"""Toetse vir stap 2: tou-variante, meetbord, oorslaanreël en eksperimente.

Voer uit met:
    python -m pytest test_groot_meet.py -q
"""

import math

import pytest

from groot_algoritmes import dijkstra
from groot_meet import (
    TelSleutel, bou_grawe, kies_pare, kruskal_eksperiment, loop_leer, meet,
    roete_eksperiment, sorteer_eksperiment,
)
from groot_tou_variante import TOU_SOORTE, kortste_pad_met_tou


@pytest.fixture(scope="module")
def grawe():
    return bou_grawe([200, 400], saad=5)


@pytest.mark.parametrize("tou_naam", list(TOU_SOORTE))
@pytest.mark.parametrize("heuristiek", [False, True])
def test_elke_tou_vind_dieselfde_tyd_as_dijkstra(grawe, tou_naam, heuristiek):
    """Drie toue, Dijkstra en A*: almal moet die minimum tyd vind (die pad mag by gelyke tye verskil)."""
    graf = grawe[400]
    for begin, doel, verwag in kies_pare(graf, 15, saad=2):
        uit = kortste_pad_met_tou(graf, begin, doel, TOU_SOORTE[tou_naam], heuristiek)
        assert math.isclose(uit.tyd_s, verwag, rel_tol=1e-9)
        assert uit.pad[0] == begin and uit.pad[-1] == doel


def test_woordeboek_tou_werk_groei_vinniger_as_hoop(grawe):
    """Die skandeertou doen baie meer werk as die hoop vir presies dieselfde roetes."""
    graf = grawe[400]
    pare = kies_pare(graf, 10, saad=2)
    werk = {naam: sum(kortste_pad_met_tou(graf, b, d, klas, False).tou_werk for b, d, _ in pare)
            for naam, klas in TOU_SOORTE.items()}
    hoop, woordeboek = werk["Binêre hoop (heapq)"], werk["Woordeboek + min()-skandering"]
    assert woordeboek > 3 * hoop


def test_tou_variante_geblokkeer_en_ongeldig(grawe):
    graf = grawe[200]
    begin, doel, _ = kies_pare(graf, 1)[0]
    klas = TOU_SOORTE["Binêre hoop (heapq)"]
    assert kortste_pad_met_tou(graf, begin, doel, klas, True, geblokkeer={doel}) is None
    with pytest.raises(ValueError):
        kortste_pad_met_tou(graf, begin, "ONBEKEND", klas, True)


def test_meet_statistiek_en_herhalings():
    """Normale funksie: volle herhalings en min <= mediaan <= maks. 'n Stadige funksie word nie herhaal nie."""
    stats, resultaat = meet(lambda: 42, herhalings=4)
    assert resultaat == 42
    assert stats["herhalings"] == 4
    assert stats["min_s"] <= stats["mediaan_s"] <= stats["maks_s"]
    teller = []
    stats, _ = meet(lambda: teller.append(1), herhalings=5, begroting_s=0.0)   # Alles is "te stadig".
    assert stats["herhalings"] == 1 and len(teller) == 1   # Net die opwarmlopie.


def test_loop_leer_slaan_oor_wat_te_stadig_sal_wees():
    """Voorspelling = vorige tyd x (n/vorige n)^2. Oor die grens: dit en alles groter word oorgeslaan."""
    tye = {100: 1.0, 200: 4.0}
    gemeet = []

    def meet_een(n):
        gemeet.append(n)
        return {"mediaan_s": tye[n]}

    rye = loop_leer([100, 200, 400, 800], meet_een, tydgrens_s=10.0)
    assert gemeet == [100, 200]                        # 400 voorspel 16 s > 10 s.
    assert [r["status"] for r in rye] == ["ok", "ok", "oorgeslaan", "oorgeslaan"]
    assert rye[2]["voorspel_s"] == pytest.approx(16.0)
    assert rye[3]["voorspel_s"] == pytest.approx(64.0)


def test_tel_sleutel_tel_vergelykings():
    TelSleutel.telling = 0
    a, b = TelSleutel(1), TelSleutel(2)
    assert a < b and not a > b and a <= b and not a >= b
    assert TelSleutel.telling == 4


def test_sorteer_eksperiment_tellings_toon_kwadraties_teenoor_nlogn(grawe):
    """Omgekeerde invoer: invoegsortering ~n²/2 vergelykings, saamsmelt ~n·log n. Reeds gesorteer: invoeg n-1."""
    nodusse = list(grawe[400].nodes.values())
    rye = sorteer_eksperiment(nodusse, [100, 400], herhalings=1)
    def tel(algoritme, patroon, n):
        return next(r["vergelykings"] for r in rye
                    if r["algoritme"] == algoritme and r["patroon"] == patroon and r["n"] == n)
    assert tel("Invoegsortering", "omgekeerd", 400) > 20 * tel("Saamsmeltsortering", "omgekeerd", 400)
    assert tel("Invoegsortering", "reeds gesorteer", 400) == 399
    # 4x meer items gee ~16x meer vergelykings (kwadraties); lineêr sou 4x gewees het.
    assert tel("Invoegsortering", "omgekeerd", 400) > 10 * tel("Invoegsortering", "omgekeerd", 100)


def test_roete_en_kruskal_eksperimente_lewer_rye_vir_elke_kombinasie(grawe):
    roete = roete_eksperiment(grawe, aantal_pare=5, herhalings=1)
    assert len(roete) == 2 * len(TOU_SOORTE) * len(grawe)
    assert all(r["status"] == "ok" and r["besoek_totaal"] > 0 for r in roete)
    kruskal_rye = kruskal_eksperiment(grawe, herhalings=1)
    assert len(kruskal_rye) == 3 * len(grawe)
    # Dieselfde spanboomgewig, ongeag die sorteermetode.
    for n in grawe:
        gewigte = {r["totale_gewig"] for r in kruskal_rye if r["n"] == n}
        assert len(gewigte) == 1
