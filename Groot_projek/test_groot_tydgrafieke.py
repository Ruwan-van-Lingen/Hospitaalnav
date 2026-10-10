"""Toetse vir stap 4b: tydgrafieke teken uit 'n klein, handgemaakte resultaatlys.

Voer uit met:
    python -m pytest test_groot_tydgrafieke.py -q
"""

import json

import pytest

from groot_tydgrafieke import laai, teken_kruskal, teken_roetes, teken_sorteer, teken_vergelykings


def stats(t):
    return {"mediaan_s": t, "min_s": t * 0.9, "maks_s": t * 1.1, "herhalings": 3}


def maak_rye():
    rye = []
    for n in (100, 200, 400):
        for patroon in ("willekeurig", "reeds gesorteer"):
            for naam, f in (("Invoegsortering", n * n), ("Saamsmeltsortering", n * 7),
                            ("Python sorted() (verwysing)", n)):
                rye.append({"eksperiment": "sortering", "algoritme": naam, "patroon": patroon, "n": n,
                            "status": "ok", **stats(f * 1e-6), "vergelykings": f})
        for alg in ("Dijkstra", "A*"):
            for tou in ("Binêre hoop (heapq)", "Woordeboek + min()-skandering", "Gesorteerde lys (bisect)"):
                rye.append({"eksperiment": "roete", "algoritme": alg, "tou": tou, "n": n, "status": "ok",
                            **stats(n * 1e-5), "pare": 5, "besoek_totaal": n * 3, "tou_werk_totaal": n * 9})
        for naam in ("Invoegsortering", "Saamsmeltsortering", "Python sorted() (verwysing)"):
            rye.append({"eksperiment": "kruskal", "algoritme": f"Kruskal + {naam}", "n": n, "status": "ok",
                        **stats(n * 1e-5), "sorteer_mediaan_s": n * 4e-6, "kante": n, "totale_gewig": 1.0,
                        "komponente": 1})
    # 'n Oorgeslane grootte moet nie die tekening breek nie.
    rye.append({"eksperiment": "sortering", "algoritme": "Invoegsortering", "patroon": "willekeurig",
                "n": 800, "status": "oorgeslaan", "voorspel_s": 99.0})
    return rye


def test_alle_grafieke_word_as_png_geskryf(tmp_path):
    rye = maak_rye()
    for naam, teken in (("a", teken_sorteer), ("b", teken_vergelykings), ("c", teken_roetes), ("d", teken_kruskal)):
        teken(rye, tmp_path / f"{naam}.png")
        assert (tmp_path / f"{naam}.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_laai_lees_die_rye_uit_stap2_json(tmp_path):
    pad = tmp_path / "r.json"
    pad.write_text(json.dumps({"omgewing": {}, "rye": maak_rye()}), encoding="utf-8")
    assert len(laai(pad)) == len(maak_rye())


def test_ontbrekende_eksperiment_gee_duidelike_fout(tmp_path):
    with pytest.raises(ValueError, match="groot_stap2"):
        teken_roetes([], tmp_path / "x.png")
