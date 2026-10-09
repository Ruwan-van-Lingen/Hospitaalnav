"""Beskerm teen dubbeldefinisies en regressies wanneer takke saamgevoeg word."""

import ast
import math
from collections import Counter
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import HospitaalGrafiek
import main
import VloerPlan
from mst_en_vloei import bereken_min_spanboom, edmonds_karp


def test_api_eindpunte_word_net_een_keer_geregistreer():
    """Geen (metode, pad)-kombinasie word dubbel geregistreer nie, bv. ná 'n merge."""
    sleutels = [
        (metode, roete.path)
        for roete in main.app.routes
        for metode in getattr(roete, "methods", [])
    ]
    assert all(telling == 1 for telling in Counter(sleutels).values())


@pytest.mark.parametrize("leer", ["main.py", "HospitaalGrafiek.py"])
def test_geen_dubbele_funksiedefinisies(leer):
    """Geen funksie of metode word twee keer in dieselfde omvang gedefinieer nie; die tweede sou die eerste stilweg vervang."""
    boom = ast.parse(Path(__file__).with_name(leer).read_text(encoding="utf-8"))
    houers = [boom] + [item for item in ast.walk(boom) if isinstance(item, ast.ClassDef)]
    for houer in houers:
        name = [item.name for item in houer.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert len(name) == len(set(name)), leer


def test_admin_en_vloerplan_gebruik_sorteeralgoritmes(monkeypatch):
    """Die admin-API en PNG-vloerplan gebruik werklik die handgeskrewe sorteerders, en die uitvoer is reg gesorteer."""
    invoeg = Mock(wraps=main.insertion_sort)
    smelt = Mock(wraps=main.merge_sort)
    vloer_invoeg = Mock(wraps=VloerPlan.insertion_sort)
    monkeypatch.setattr(main, "insertion_sort", invoeg)
    monkeypatch.setattr(main, "merge_sort", smelt)
    monkeypatch.setattr(VloerPlan, "insertion_sort", vloer_invoeg)
    with TestClient(main.app) as client:
        assert client.post("/admin/login", json={"gebruikersnaam": "admin", "wagwoord": "admin"}).status_code == 200
        kaart = client.get("/admin/map").json()
        assert invoeg.call_count > 0
        assert smelt.call_count > 0
        geboue = kaart["geboue"]
        assert [g["naam"] for g in geboue] == sorted(g["naam"] for g in geboue)
        for gebou in geboue:
            vlakke = [v["level_nommer"] for v in gebou["vloere"]]
            assert vlakke == sorted(vlakke)
            for vloer in gebou["vloere"]:
                etikette = [n["etiket"] for n in vloer["nodes"]]
                assert etikette == sorted(etikette)
        gesluit = ["SYGEBOU-1-RAD", "MAIN-1-WARDA"]
        assert client.post("/admin/incident", json={"kode_id": "ONDERHOUD", "node_ids": gesluit}).status_code == 200
        assert client.get("/incident").json()["blocked_node_ids"] == sorted(gesluit)
        prent = client.get("/route/image", params={"begin": "MAIN-G-ENT", "doel": "MAIN-G-ER"})
        assert prent.status_code == 200
        assert vloer_invoeg.call_count == 1


def test_selfstandige_spanboom_aanvaar_eenmalige_nodusiterator():
    """Kruskal werk ook met 'n iterator wat net een keer gelees kan word."""
    rande, gewig = bereken_min_spanboom(iter("ABC"), [("A", "B", 2), ("B", "C", 3), ("A", "C", 9)])
    assert rande == [("A", "B", 2), ("B", "C", 3)]
    assert gewig == 5


def test_selfstandige_spanboom_valideer_eindpunte_en_gewigte():
    """Kruskal verwerp 'n rand met 'n onbekende eindpunt of 'n oneindige gewig."""
    with pytest.raises(ValueError):
        bereken_min_spanboom("AB", [("A", "C", 1)])
    with pytest.raises(ValueError):
        bereken_min_spanboom("AB", [("A", "B", math.inf)])


def test_selfstandige_vloei_behou_minimumsnit_met_iterator():
    """Edmonds-Karp lewer die korrekte min-snit met 'n eenmalige iterator, sonder om die invoer te verander."""
    kante = [("S", "A", 3), ("A", "T", 2), ("S", "T", 1)]
    assert edmonds_karp(iter(kante), "S", "T") == (3, [("A", "T", 2), ("S", "T", 1)])
    assert kante == [("S", "A", 3), ("A", "T", 2), ("S", "T", 1)]


def test_selfstandige_vloei_bron_is_put_en_onbereikbare_put():
    """Bron gelyk aan put, of 'n onbereikbare put, gee vloei 0."""
    assert edmonds_karp([("S", "T", 2)], "S", "S") == (0, [])
    assert edmonds_karp([("S", "A", 2)], "S", "T") == (0, [])


@pytest.mark.parametrize("kapasiteit", [-1, math.inf, -math.inf, math.nan])
def test_selfstandige_vloei_verwerp_ongeldige_kapasiteit(kapasiteit):
    """Negatiewe, oneindige en NaN-kapasiteite word geweier."""
    with pytest.raises(ValueError):
        edmonds_karp([("S", "T", kapasiteit)], "S", "T")


def test_grafiek_gebruik_die_algoritmes_in_mst_en_vloei(monkeypatch):
    """Kruskal en Edmonds-Karp mag net in mst_en_vloei.py bestaan, nie ook in HospitaalGrafiek nie."""
    kruskal = Mock(wraps=HospitaalGrafiek.kruskal_spanboom)
    vloei = Mock(wraps=HospitaalGrafiek.edmonds_karp)
    monkeypatch.setattr(HospitaalGrafiek, "kruskal_spanboom", kruskal)
    monkeypatch.setattr(HospitaalGrafiek, "edmonds_karp", vloei)
    with TestClient(main.app) as client:
        assert client.post("/admin/login", json={"gebruikersnaam": "admin", "wagwoord": "admin"}).status_code == 200
        assert client.get("/analise/spanboom").status_code == 200
        assert client.get("/analise/maks_vloei", params={"bron": "MAIN-G-ER"}).status_code == 200
    assert kruskal.call_count == 1
    assert vloei.call_count == 1
