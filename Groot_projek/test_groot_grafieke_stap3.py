"""Toetse vir stap 4c: lambda-, parallel- en spanboomgrafieke.

Voer uit met:
    python -m pytest test_groot_grafieke_stap3.py -q
"""

import pytest

from groot_data import genereer_toetsdata
from groot_grafieke_stap3 import teken_lambda, teken_parallel, teken_spanboom


def stats(t):
    return {"mediaan_s": t, "min_s": t, "maks_s": t, "herhalings": 1}


LAMBDA = [{"eksperiment": e, "variant": v, "n": 100, "aanroepe": 100, "status": "ok", **stats(t)}
          for e in ("afstand", "gewig") for v, t in (("lambda", 3e-3), ("def", 3e-3), ("inline", 2e-3))]
DEKKING = [{"n": n, "status": "ok", "onbereikbaar": 3, **stats(n / 100), "sekwensieel": stats(n / 100),
            "parallel": {"1": {"een taak per nodus": stats(n / 90), "brokke": stats(n / 120)},
                         "2": {"een taak per nodus": stats(n / 150), "brokke": stats(n / 200)}}}
           for n in (200, 400)]


def is_png(pad):
    return pad.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_lambda_en_parallel_grafieke(tmp_path):
    teken_lambda(LAMBDA, tmp_path / "a.png")
    teken_parallel(DEKKING, 1, tmp_path / "b.png")
    teken_parallel(DEKKING, 4, tmp_path / "c.png")
    assert all(is_png(tmp_path / f"{x}.png") for x in "abc")


def test_spanboomgrafiek_vir_een_vloer(tmp_path):
    teken_spanboom(genereer_toetsdata(200, 3, saad=1), 1, tmp_path / "s.png")
    assert is_png(tmp_path / "s.png")


def test_leë_resultate_gee_duidelike_fout(tmp_path):
    with pytest.raises(ValueError, match="groot_stap3"):
        teken_lambda([], tmp_path / "x.png")
    with pytest.raises(ValueError, match="groot_stap3"):
        teken_parallel([], 1, tmp_path / "y.png")
