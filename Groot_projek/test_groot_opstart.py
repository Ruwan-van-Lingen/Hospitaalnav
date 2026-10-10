"""Die openbare stapopdragte moet werk sonder 'n handgestelde PYTHONPATH."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("stap", ["1", "2", "3", "4a", "4b", "4c"])
def test_stap_begin_vanaf_enige_werkgids(stap, tmp_path):
    skrip = Path(__file__).with_name(f"groot_stap{stap}.py").resolve()
    omgewing = dict(os.environ)
    omgewing.pop("PYTHONPATH", None)
    uitslag = subprocess.run(
        [sys.executable, str(skrip), "--help"], cwd=tmp_path,
        env=omgewing, capture_output=True, text=True, timeout=30,
    )
    assert uitslag.returncode == 0, uitslag.stderr
    assert "--help" in uitslag.stdout


@pytest.mark.parametrize("uitgang", ["0", "1"])
def test_stap1_hanteer_csv_sonder_bereikbare_pare(uitgang, tmp_path):
    nodusse = tmp_path / "nodusse.csv"
    rande = tmp_path / "rande.csv"
    nodusse.write_text(
        "node_id,etiket,vloer,pos_x,pos_y,tipe_kode,is_nooduitgang\n"
        f"A,A,0,0,0,DEPARTEMENT,{uitgang}\nB,B,0,3,0,DEPARTEMENT,0\n",
        encoding="utf-8",
    )
    rande.write_text("van_node,na_node,rand_tipe,afstand_m,gewig_s,kapasiteit,bidirectional\n", encoding="utf-8")
    uitslag = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("groot_stap1.py")), "--csv", str(nodusse), str(rande)],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert uitslag.returncode == 0, uitslag.stderr
    assert "geen bereikbare pare" in uitslag.stdout
    assert "geen positiewe deurvloei" in uitslag.stdout
