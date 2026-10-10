"""Toetse vir stap 4a: bottelnekberekeninge en grafieke.

Voer uit met:
    python -m pytest test_groot_grafieke.py -q
"""

import pytest

from groot_algoritmes import maks_vloei_na_uitgange
from groot_data import genereer_toetsdata
from groot_grafieke import (
    bottelnek_per_vloer, skaleer_tipe, teken_sykant, teken_vloere, teken_wat_as, wat_as_reeks,
)


@pytest.fixture(scope="module")
def graf():
    return genereer_toetsdata(400, 4, saad=3)


def test_snitkapasiteit_gelyk_aan_vloei_en_boonste_vloer_is_trappe(graf):
    rye = bottelnek_per_vloer(graf)
    assert [r["vloer"] for r in rye] == [3, 2, 1, 0]
    for r in rye:
        assert sum(k for _, _, k in r["bottelnekke"]) == pytest.approx(r["vloei"])
    assert rye[0]["hoof_tipe"] == "TRAPPE"


def test_skaleer_tipe_verander_net_daardie_tipe_en_laat_die_oorspronklike_heel(graf):
    voor = list(graf.rande_lys)
    groter = skaleer_tipe(graf, "TRAPPE", 3)
    assert graf.rande_lys == voor
    assert len(groter.rande_lys) == len(voor)
    for oud, nuut in zip(voor, groter.rande_lys):
        assert nuut[5] == (oud[5] * 3 if oud[2] == "TRAPPE" else oud[5])


def test_breër_trappe_gee_nooit_minder_vloei(graf):
    reeks = wat_as_reeks(graf, 3, faktore=(1, 2, 4))
    vloei = [r["vloei"] for r in reeks]
    assert vloei == sorted(vloei) and vloei[-1] > vloei[0]
    assert reeks[0]["trappe_is_bottelnek"]


def test_grafieke_word_as_png_geskryf(graf, tmp_path):
    rye = bottelnek_per_vloer(graf)
    teken_vloere(rye, tmp_path / "a.png")
    teken_sykant(graf, rye[0], tmp_path / "b.png")
    teken_wat_as(wat_as_reeks(graf, 3, faktore=(1, 2)), 3, tmp_path / "c.png")
    for naam in "abc":
        assert (tmp_path / f"{naam}.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
