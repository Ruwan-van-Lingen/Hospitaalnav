"""Toetse vir stap 3: lambda-variante, groot grafiek in SQLite en parallelle dekking.

Voer uit met:
    python -m pytest test_groot_stap3.py -q
"""

import math
import sqlite3

import pytest

from HospitaalGrafiek import BEREKEN_AFSTAND, BEREKEN_GEWIG, HospitaalGrafiek, kontroleer_alle_nodusse_dekking
from groot_data import genereer_toetsdata
from groot_lambda import EKSPERIMENTE, afstand_def, gewig_def, lambda_eksperiment, maak_data
from groot_parallel import (
    dekking_een, dekking_in_brokke, kies_sluiting, maak_poel, skryf_db,
)


@pytest.fixture(scope="module")
def graf():
    return genereer_toetsdata(200, 3, saad=4)


@pytest.fixture
def db(graf, tmp_path):
    return skryf_db(graf, tmp_path / "groot.db")


def test_def_en_lambda_gee_dieselfde_antwoorde():
    assert afstand_def((0, 0), (3, 4)) == BEREKEN_AFSTAND((0, 0), (3, 4)) == 5.0
    assert gewig_def(8, 25) == BEREKEN_GEWIG(8, 25) == 33.0


def test_alle_varianta_stem_ooreen_en_eksperiment_lewer_alle_rye():
    rye = lambda_eksperiment([300], herhalings=1)
    assert len(rye) == sum(len(v) for v in EKSPERIMENTE.values())
    assert all(r["status"] == "ok" and r["aanroepe"] == 300 for r in rye)
    # Dieselfde data gee dieselfde uitkoms, so 'n tweede lopie gee dieselfde syfers.
    assert maak_data(50) == maak_data(50)


def test_skryf_db_laai_met_die_projek_se_hospitaalgrafiek(graf, db):
    hg = HospitaalGrafiek(str(db))
    assert set(hg.nodes) == set(graf.nodes)
    assert {n for n, d in hg.nodes.items() if d["is_nooduitgang"]} == set(graf.nooduitgange())
    # Elke bidirectionele rand wag in albei nodusse se lyste.
    assert sum(len(r) for r in hg.adjacency.values()) == sum(len(r) for r in graf.adjacency.values())
    with sqlite3.connect(db) as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_sluiting_is_herhaalbaar_en_laat_uitgange_oop(graf):
    a, b = kies_sluiting(graf, 0.1, saad=1), kies_sluiting(graf, 0.1, saad=1)
    assert a == b and a
    assert not a & set(graf.nooduitgange())


def test_parallel_en_brokke_stem_ooreen_met_sekwensieel(graf, db):
    hoof = HospitaalGrafiek(str(db))
    gesluit = kies_sluiting(graf, 0.1)
    verwag = kontroleer_alle_nodusse_dekking(hoof, "PUBLIEK", gesluit)
    assert any(not r["bereikbaar"] for r in verwag)
    poel = maak_poel(db, 2)
    try:
        assert dekking_in_brokke(list(hoof.nodes), "PUBLIEK", gesluit, poel, 2) == verwag
    finally:
        poel.shutdown(wait=True)


def test_dekking_een_gee_volledige_uitslag(graf):
    uit = dekking_een(graf, [1], sluit_deel=0.05, herhalings=1)
    assert uit["stem_ooreen"] is True
    assert uit["nodusse"] == 200
    assert set(uit["parallel"][1]) == {"een taak per nodus", "brokke"}
    assert all(math.isfinite(p["versnelling"]) for p in uit["parallel"][1].values())
