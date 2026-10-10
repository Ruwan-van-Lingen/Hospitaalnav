"""Data vir die groot-datastel-vertoning: CSV-laai, CSV-stoor en 'n toetsdatagenerator.

Die egte ~2000 datapunte word later hier gekoppel. Tot dan kan
genereer_toetsdata() 'n hospitaalagtige grafiek van enige grootte maak,
sodat al die algoritmes en grafieke reeds getoets kan word.

Verwagte CSV-formaat
--------------------
nodusse.csv (een ry per nodus):
    node_id, etiket, vloer, pos_x, pos_y, tipe_kode, is_nooduitgang
    - vloer           : vloervlak as heelgetal (0 = grondvloer).
    - pos_x, pos_y    : meter; A* en die grafieke gebruik dit.
    - is_nooduitgang  : 1/0 (ook true/false of ja/nee word aanvaar).

rande.csv (een ry per rand):
    van_node, na_node, rand_tipe, afstand_m, gewig_s, kapasiteit, bidirectional
    - gewig_s         : reistyd in sekondes (basis + wagtyd saam).
    - kapasiteit      : persone per sekonde; leeg = VERSTEK_KAPASITEIT.
    - bidirectional   : 1/0; leeg = 1.

Het die egte data ander kolomname, pas slegs laai_csv() aan; niks anders
in die vertoning hoef te verander nie.
"""

import csv
import math
import random
from pathlib import Path

from groot_algoritmes import GrootGrafiek, VERSTEK_KAPASITEIT
from mst_en_vloei import UnionFind

NODUS_KOLOMME = ["node_id", "etiket", "vloer", "pos_x", "pos_y", "tipe_kode", "is_nooduitgang"]
RAND_KOLOMME = ["van_node", "na_node", "rand_tipe", "afstand_m", "gewig_s", "kapasiteit", "bidirectional"]

# Woorde waaruit toetsetikette saamgestel word; 'n mengsel gee 'n realistiese
# (nie reeds gesorteerde) volgorde vir die sorteervergelyking.
ETIKET_WOORDE = ["Saal", "Kliniek", "Stoor", "Kantoor", "Laboratorium",
                 "Spreekkamer", "Apteek", "Wagkamer", "Teater", "Ontvangs"]


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def _lees_getal(waarde, veld, reel):
    """Skakel teks na 'n eindige, nie-negatiewe getal, of gooi 'n duidelike fout met die reëlnommer."""
    try:
        getal = float(waarde)
    except (TypeError, ValueError):
        raise ValueError(f"Reël {reel}: '{veld}' is nie 'n getal nie ({waarde!r}).") from None
    if not math.isfinite(getal) or getal < 0:
        raise ValueError(f"Reël {reel}: '{veld}' moet eindig en nie-negatief wees ({waarde!r}).")
    return getal


def _lees_vlag(waarde, verstek):
    """'1', 'true', 'ja' en 'waar' is waar; leeg gebruik die verstek."""
    if waarde is None or str(waarde).strip() == "":
        return verstek
    return str(waarde).strip().lower() in ("1", "true", "ja", "waar")


def _kontroleer_kolomme(lees, vereis, leernaam):
    """Gooi 'n fout as 'n vereiste kolom in die CSV-opskrif ontbreek."""
    ontbreek = [k for k in vereis if k not in (lees.fieldnames or [])]
    if ontbreek:
        raise ValueError(f"{leernaam}: kolom(me) ontbreek: {', '.join(ontbreek)}")


def laai_csv(nodusse_pad, rande_pad) -> GrootGrafiek:
    """Lees die twee CSV-lêers in 'n GrootGrafiek."""
    graf = GrootGrafiek()

    with open(nodusse_pad, newline="", encoding="utf-8") as leer:
        lees = csv.DictReader(leer)
        _kontroleer_kolomme(lees, NODUS_KOLOMME, str(nodusse_pad))
        for reel, ry in enumerate(lees, start=2):   # Reël 1 is die opskrif.
            # Vloer en koördinate mag negatief wees (kelders), daarom nie _lees_getal nie.
            graf.voeg_nodus_by(
                ry["node_id"].strip(), ry["etiket"].strip(), int(float(ry["vloer"])),
                float(ry["pos_x"]), float(ry["pos_y"]),
                ry["tipe_kode"].strip() or "DEPARTEMENT",
                _lees_vlag(ry["is_nooduitgang"], False),
            )

    with open(rande_pad, newline="", encoding="utf-8") as leer:
        lees = csv.DictReader(leer)
        _kontroleer_kolomme(lees, RAND_KOLOMME, str(rande_pad))
        for reel, ry in enumerate(lees, start=2):
            kapasiteit = (VERSTEK_KAPASITEIT if str(ry["kapasiteit"]).strip() == ""
                          else _lees_getal(ry["kapasiteit"], "kapasiteit", reel))
            graf.voeg_rand_by(
                ry["van_node"].strip(), ry["na_node"].strip(), ry["rand_tipe"].strip() or "GANG",
                _lees_getal(ry["afstand_m"], "afstand_m", reel),
                _lees_getal(ry["gewig_s"], "gewig_s", reel),
                kapasiteit,
                _lees_vlag(ry["bidirectional"], True),
            )
    return graf


def stoor_csv(graf, nodusse_pad, rande_pad):
    """Skryf 'n grafiek na CSV (bv. die gegenereerde toetsdata, as voorbeeld van die formaat)."""
    with open(nodusse_pad, "w", newline="", encoding="utf-8") as leer:
        skryf = csv.writer(leer)
        skryf.writerow(NODUS_KOLOMME)
        for n in graf.nodes.values():
            skryf.writerow([n["node_id"], n["etiket"], n["vloer"], n["pos"][0], n["pos"][1],
                            n["tipe_kode"], int(n["is_nooduitgang"])])
    with open(rande_pad, "w", newline="", encoding="utf-8") as leer:
        skryf = csv.writer(leer)
        skryf.writerow(RAND_KOLOMME)
        for van, na, tipe, afstand, gewig, kap, bi in graf.rande_lys:
            skryf.writerow([van, na, tipe, afstand, gewig, kap, int(bi)])


# ---------------------------------------------------------------------------
# Toetsdatagenerator
# ---------------------------------------------------------------------------

def genereer_toetsdata(aantal_nodusse=2000, aantal_vloere=5, saad=42,
                       ekstra_rand_kans=0.35) -> GrootGrafiek:
    """Bou 'n hospitaalagtige grafiek: elke vloer is 'n rooster van nodusse.

    • Elke vloer is gewaarborg verbind (ewekansige spanboom), plus 'n deel
      van die oorblywende roosterrande vir omweë.
    • Vier trappe en een hysbak verbind opeenvolgende vloere. Trappe het 'n
      lae kapasiteit, sodat hulle die bottelnekke is wat die vertoning wys.
    • Nooduitgange lê aan die rand van die grondvloer.
    Dieselfde saad gee altyd dieselfde grafiek, sodat resultate herhaalbaar is.
    """
    if aantal_nodusse < aantal_vloere * 4:
        raise ValueError("Minstens 4 nodusse per vloer word benodig.")
    rng = random.Random(saad)
    graf = GrootGrafiek()
    MAAT = 3.0  # Gemiddelde meter tussen buurnodusse.

    per_vloer = math.ceil(aantal_nodusse / aantal_vloere)
    sy = math.ceil(math.sqrt(per_vloer))            # Die rooster is sy x sy (laaste vloer dalk gedeeltelik).
    plek: dict[tuple[int, int, int], str] = {}      # (vloer, x, y) -> node_id

    # --- Nodusse ---
    for indeks in range(aantal_nodusse):
        vloer, binne = divmod(indeks, per_vloer)
        y, x = divmod(binne, sy)
        node_id = f"V{vloer}-{x:02d}-{y:02d}"
        rand_van_gebou = x in (0, sy - 1) or y in (0, sy - 1)
        is_uitgang = vloer == 0 and ((rand_van_gebou and (x + y) % 6 == 0) or (x, y) == (0, 0))
        etiket = f"{rng.choice(ETIKET_WOORDE)} {rng.randint(1, 99)}"
        graf.voeg_nodus_by(node_id, etiket, vloer, x * MAAT, y * MAAT,
                           "INGANG" if is_uitgang else "DEPARTEMENT", is_uitgang)
        plek[(vloer, x, y)] = node_id
    aantal_werklike_vloere = max(v for v, _, _ in plek) + 1

    # --- Gange binne elke vloer ---
    for vloer in range(aantal_werklike_vloere):
        ids = [nid for (v, _, _), nid in plek.items() if v == vloer]
        kandidate = []
        for (v, x, y), nid in plek.items():
            if v != vloer:
                continue
            for dx, dy in ((1, 0), (0, 1)):         # Net regs en onder, sodat geen rand dubbel is nie.
                buur = plek.get((vloer, x + dx, y + dy))
                if buur:
                    kandidate.append((nid, buur))
        rng.shuffle(kandidate)

        uf = UnionFind(ids)
        for a, b in kandidate:
            verplig = uf.unie(a, b)                 # True = hierdie rand verbind twee dele (nodig vir verbinding).
            if verplig or rng.random() < ekstra_rand_kans:
                afstand = MAAT * rng.uniform(0.8, 1.4)
                graf.voeg_rand_by(a, b, "GANG", afstand, afstand / 1.2,
                                  rng.choice([2.0, 3.0, 4.0, 6.0]))

    # --- Trappe en hysbak tussen vloere ---
    trap_kolomme = sorted({0, sy // 3, (2 * sy) // 3, sy - 1})
    for vloer in range(1, aantal_werklike_vloere):
        for x in trap_kolomme:
            onder, bo = plek.get((vloer - 1, x, 0)), plek.get((vloer, x, 0))
            if onder and bo:
                graf.voeg_rand_by(onder, bo, "TRAPPE", 0.0, 15.0, 2.0)
                graf.nodes[onder]["tipe_kode"] = graf.nodes[bo]["tipe_kode"] = "TRAPHUIS"
        onder, bo = plek.get((vloer - 1, sy // 2, 1)), plek.get((vloer, sy // 2, 1))
        if onder and bo:
            # Hysbak: wagtyd 25 s + 8 s rit; kapasiteit is laag. Word by ontruiming uitgesluit.
            graf.voeg_rand_by(onder, bo, "HUISBAK", 0.0, 33.0, 1.5)
            graf.nodes[onder]["tipe_kode"] = graf.nodes[bo]["tipe_kode"] = "HUISBAK_GROEP"
    return graf
