"""Stap 3b: ontruimingsdekking, sekwensieel teenoor parallel, op die groot datastel.

Hierdie lêer gebruik die projek se EGTE kode: HospitaalGrafiek,
kontroleer_alle_nodusse_dekking (sekwensieel), kontroleer_alle_nodusse_dekking_parallel
en init_werker (parallel). Net die invoer is nuut: die groot grafiek word in 'n
tydelike SQLite-databasis met die projek se eie Skema.sql geskryf, sodat
HospitaalGrafiek dit kan laai asof dit die hospitaal is. Niks bestaande verander nie.

Drie metodes word vergelyk, op presies dieselfde nodusse en sluitings:
  1. sekwensieel          - een proses, een nodus op 'n slag (die basislyn).
  2. parallel, 1 taak/nodus - soos main.py dit doen (kry_dekking_pool).
  3. parallel, brokke     - EIE variant: een taak per brok nodusse; sê minder
                            heen-en-weer tussen prosesse. Wys waar die oorhoofse
                            koste van (2) heen gaan.
Elke parallelle uitkoms moet presies gelyk wees aan die sekwensiële een.

LET WEL: parallelle spoed hang af van hoeveel kerne die rekenaar het. Op een
kern kan parallel nie wen nie. Die kerne word saam met die resultate gestoor.
"""

import math
import os
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
from multiprocessing import get_context
from pathlib import Path
import random
import time

from groot_paaie import HOOF_GIDS, maak_hoofprojek_beskikbaar

maak_hoofprojek_beskikbaar()

import HospitaalGrafiek as hg
from HospitaalGrafiek import (
    HospitaalGrafiek, init_werker, kontroleer_alle_nodusse_dekking,
    kontroleer_alle_nodusse_dekking_parallel, kontroleer_nodus_dekking,
)
from groot_meet import meet

SKEMA_PAD = HOOF_GIDS / "Skema.sql"


# ---------------------------------------------------------------------------
# Groot grafiek -> SQLite in die projek se skema
# ---------------------------------------------------------------------------

def skryf_db(graf, db_pad, skema_pad=SKEMA_PAD):
    """Skryf 'n GrootGrafiek na 'n nuwe SQLite-databasis met die projek se Skema.sql.

    Een gebou, een vloer per vloervlak. tipe_kode moet in node_tipes bestaan.
    Rande word een keer geskryf met hul bidirectional-vlag; HospitaalGrafiek
    voeg self die omgekeerde rand by, net soos met die hospitaaldata.
    """
    db_pad = Path(db_pad)
    if db_pad.exists():
        db_pad.unlink()
    with closing(sqlite3.connect(db_pad)) as conn:
        conn.executescript(Path(skema_pad).read_text(encoding="utf-8"))
        conn.execute("INSERT INTO geboue (gebou_id, naam) VALUES ('GROOT', 'Groot datastel')")
        vlakke = sorted({n["vloer"] for n in graf.nodes.values()})
        conn.executemany(
            "INSERT INTO vloere (vloer_id, gebou_id, level_nommer, naam) VALUES (?, 'GROOT', ?, ?)",
            [(f"GROOT-{v}", v, f"Vlak {v}") for v in vlakke],
        )
        conn.executemany(
            """INSERT INTO nodes (node_id, vloer_id, tipe_kode, etiket, pos_x, pos_y,
                                  is_beperk, beperkte_groep, is_nooduitgang)
               VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?)""",
            [(n["node_id"], f"GROOT-{n['vloer']}", n["tipe_kode"], n["etiket"],
              n["pos"][0], n["pos"][1], int(n["is_nooduitgang"])) for n in graf.nodes.values()],
        )
        conn.executemany(
            """INSERT INTO rande (van_node, na_node, rand_tipe, afstand_m, basis_gewig_s,
                                  wag_penalty_s, vloer_verander, bidirectional, kapasiteit)
               VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)""",
            [(van, na, tipe, afstand, gewig,
              abs(graf.nodes[van]["vloer"] - graf.nodes[na]["vloer"]), int(bi), kap)
             for van, na, tipe, afstand, gewig, kap, bi in graf.rande_lys],
        )
        conn.commit()
    return db_pad


def kies_sluiting(graf, deel, saad=5):
    """Ewekansige stel geblokkeerde nodusse ('deel' van almal); nooduitgange bly oop vir 'n sinvolle toets."""
    rng = random.Random(saad)
    kandidate = [n for n, d in graf.nodes.items() if not d["is_nooduitgang"]]
    return set(rng.sample(kandidate, round(len(kandidate) * deel)))


# ---------------------------------------------------------------------------
# Die eie brokvariant (hergebruik die projek se werkerinisialisering)
# ---------------------------------------------------------------------------

def _brok_taak(node_ids, gebruiker_tipe, geblokkeer):
    """Loop in 'n werkproses oor 'n hele brok nodusse; gebruik die graf wat init_werker gelaai het."""
    if hg._WERKER_GRAF is None:
        raise RuntimeError("_WERKER_GRAF is nie geïnitialiseer nie (init_werker het nie geloop nie).")
    return [kontroleer_nodus_dekking(hg._WERKER_GRAF, nid, gebruiker_tipe, geblokkeer)
            for nid in node_ids]


def dekking_in_brokke(node_ids, gebruiker_tipe, geblokkeer, uitvoerder, werkers):
    """Soos kontroleer_alle_nodusse_dekking_parallel, maar met een taak per brok. Behou die invoervolgorde."""
    node_ids = list(node_ids)
    grootte = max(1, math.ceil(len(node_ids) / (werkers * 4)))
    take = [uitvoerder.submit(_brok_taak, node_ids[i:i + grootte], gebruiker_tipe, geblokkeer)
            for i in range(0, len(node_ids), grootte)]
    return [r for taak in take for r in taak.result()]


def maak_poel(db_pad, werkers):
    """Dieselfde poel as main.kry_dekking_pool: 'spawn', met init_werker as initializer."""
    return ProcessPoolExecutor(max_workers=werkers, mp_context=get_context("spawn"),
                               initializer=init_werker, initargs=(str(db_pad),))


# ---------------------------------------------------------------------------
# Die eksperiment
# ---------------------------------------------------------------------------

def standaard_werkers():
    """Een, twee en (as die rekenaar dit het) vier werkers, nooit meer as die kerne nie."""
    kerne = os.cpu_count() or 1
    return sorted({1, min(2, kerne), min(4, kerne)})


def dekking_een(graf, werkers_lys, sluit_deel=0.05, herhalings=3, gebruiker_tipe="PUBLIEK", werkgids=None):
    """Meet sekwensieel en parallel (twee soorte) op een grafiek; kontroleer dat alles ooreenstem.

    Gee 'n woordeboek met 'mediaan_s' (= sekwensieel, soos loop_leer verwag) en
    per werkertal die opstartkoste en die warm tye van beide parallelle metodes.
    Opstart = poel skep + eerste volledige lopie (elke werker laai sy eie grafiek).
    """
    with tempfile.TemporaryDirectory(dir=werkgids) as gids:
        db_pad = skryf_db(graf, Path(gids) / "groot.db")
        t0 = time.perf_counter()
        hoof = HospitaalGrafiek(str(db_pad))
        laai_s = time.perf_counter() - t0
        geblokkeer = kies_sluiting(graf, sluit_deel)
        node_ids = list(hoof.nodes)

        sek_stats, verwag = meet(
            lambda: kontroleer_alle_nodusse_dekking(hoof, gebruiker_tipe, geblokkeer), herhalings)
        onbereikbaar = sum(1 for r in verwag if not r["bereikbaar"])

        parallel = {}
        for w in werkers_lys:
            pak = {}
            for naam, funksie in (
                ("een taak per nodus",
                 lambda p, w=w: kontroleer_alle_nodusse_dekking_parallel(node_ids, gebruiker_tipe, geblokkeer, p)),
                ("brokke",
                 lambda p, w=w: dekking_in_brokke(node_ids, gebruiker_tipe, geblokkeer, p, w)),
            ):
                poel = maak_poel(db_pad, w)
                try:
                    t0 = time.perf_counter()
                    eerste = funksie(poel)            # Sluit werkerbegin en grafieklaai in.
                    opstart_s = time.perf_counter() - t0
                    if eerste != verwag:
                        raise RuntimeError(f"Parallel '{naam}' ({w} werkers) verskil van sekwensieel.")
                    stats, uit = meet(lambda: funksie(poel), herhalings)
                    if uit != verwag:
                        raise RuntimeError(f"Parallel '{naam}' ({w} werkers) verskil van sekwensieel.")
                finally:
                    poel.shutdown(wait=True)
                pak[naam] = {**stats, "opstart_s": opstart_s,
                             "versnelling": sek_stats["mediaan_s"] / stats["mediaan_s"]}
            parallel[w] = pak
    return {**sek_stats, "nodusse": len(node_ids), "rande": len(graf.rande_lys),
            "geblokkeer": len(geblokkeer), "onbereikbaar": onbereikbaar,
            "grafiek_laai_s": laai_s, "sekwensieel": sek_stats, "parallel": parallel,
            "stem_ooreen": True}
