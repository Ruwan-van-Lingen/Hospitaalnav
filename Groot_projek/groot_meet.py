"""Meetbord vir die groot-datastel-vertoning: tellings EN tye, herhaald en met 'n tydgrens.

Twee soorte syfers word hier gemeet:
  • TELLINGS (vergelykings, nodusse uitgebrei, touwerk, vloei): hang net van die
    data en die algoritme af, dus dieselfde elke keer en op elke rekenaar.
  • TYE (sekondes): hang van die rekenaar af. Daarom word elke tyd herhaal
    (ná 'n opwarmlopie) en wys ons die mediaan, die minimum en die maksimum.

Metodes wat te stadig sou wees, word nie ontplooi nie. Ons voorspel die volgende
grootte se tyd as vorige_tyd × (n / vorige_n)², wat die kwadratiese
slegste geval veronderstel. Is die voorspelling oor die tydgrens, word dit en
alles groter oorgeslaan en as 'oorgeslaan' aangeteken. Dit is self 'n resultaat:
die metode is nie geskik vir hierdie hoeveelheid data nie.
"""

import math
import os
import platform
import random
import statistics
import sys
import time
from datetime import datetime

from groot_algoritmes import SORTEER_METODES, dijkstra, kruskal
from groot_data import genereer_toetsdata
from groot_tou_variante import TOU_SOORTE, kortste_pad_met_tou
from mst_en_vloei import bereken_min_spanboom

STANDAARD_TYDGRENS_S = 20.0   # Langste voorspelde tyd vir een meting.
METING_BEGROTING_S = 6.0      # Hoeveel sekondes ons hoogstens aan herhalings van een meting spandeer.
SORTEER_PATRONE = ("willekeurig", "reeds gesorteer", "omgekeerd")


# ---------------------------------------------------------------------------
# Hulpmiddels
# ---------------------------------------------------------------------------

def meet(funksie, herhalings=5, begroting_s=METING_BEGROTING_S):
    """Voer funksie een keer ter opwarming uit, en dan tot 'herhalings' keer gemeet.

    Duur die opwarmlopie lank, word minder (of geen) herhalings gedoen, sodat
    stadige metodes nie die hele vertoning oorneem nie. Gee (statistiek, laaste resultaat).
    """
    begin = time.perf_counter()
    resultaat = funksie()
    eerste = max(time.perf_counter() - begin, 1e-9)

    if eerste >= begroting_s:
        tye = [eerste]            # Te stadig om te herhaal; die opwarmlopie is self die meting.
    else:
        aantal = max(1, min(herhalings, int(begroting_s / eerste)))
        tye = []
        for _ in range(aantal):
            begin = time.perf_counter()
            resultaat = funksie()
            tye.append(time.perf_counter() - begin)
    return {
        "mediaan_s": statistics.median(tye),
        "min_s": min(tye),
        "maks_s": max(tye),
        "herhalings": len(tye),
    }, resultaat


class TelSleutel:
    """Sorteersleutel wat tel hoeveel keer dit vergelyk word (Sorteer.py gebruik >, <= en <)."""
    __slots__ = ("waarde",)
    telling = 0

    def __init__(self, waarde):
        self.waarde = waarde

    def __lt__(self, ander):
        TelSleutel.telling += 1
        return self.waarde < ander.waarde

    def __gt__(self, ander):
        TelSleutel.telling += 1
        return self.waarde > ander.waarde

    def __le__(self, ander):
        TelSleutel.telling += 1
        return self.waarde <= ander.waarde

    def __ge__(self, ander):
        TelSleutel.telling += 1
        return self.waarde >= ander.waarde


def loop_leer(groottes, meet_een, tydgrens_s, voorbeeld_velde=None):
    """Meet 'n metode op elke grootte (klein na groot) en slaan oor wat te stadig sal wees.

    meet_een(n) gee 'n woordeboek met minstens 'mediaan_s'. Elke ry kry 'n
    'status': 'ok' of 'oorgeslaan' (met die voorspelde tyd).
    """
    rye = []
    vorige = None          # (n, mediaan_s) van die laaste suksesvolle meting.
    stop = False
    for n in sorted(groottes):
        if vorige and not stop:
            voorspel = vorige[1] * (n / vorige[0]) ** 2
            stop = voorspel > tydgrens_s
        if stop:
            rye.append({"n": n, "status": "oorgeslaan",
                        "voorspel_s": vorige[1] * (n / vorige[0]) ** 2})
            continue
        uitslag = meet_een(n)
        rye.append({"n": n, "status": "ok", **uitslag})
        vorige = (n, max(uitslag["mediaan_s"], 1e-9))
    return rye


def bou_grawe(groottes, saad=42):
    """Genereer 'n grafiek per grootte; die aantal vloere groei saam (omtrent 400 nodusse per vloer)."""
    return {n: genereer_toetsdata(n, max(3, round(n / 400)), saad) for n in sorted(groottes)}


def omgewing(instellings):
    """Inligting oor die rekenaar en lopie, sodat gestoorde resultate later verstaanbaar bly."""
    return {
        "datum": datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "verwerker": platform.processor() or "onbekend",
        "kerne": os.cpu_count(),
        "instellings": instellings,
    }


# ---------------------------------------------------------------------------
# Eksperiment 1: sortering
# ---------------------------------------------------------------------------

def _maak_patroon(items, patroon, saad):
    """Gee die items in die gevraagde beginvolgorde (voor sortering)."""
    if patroon == "willekeurig":
        kopie = list(items)
        random.Random(saad).shuffle(kopie)
        return kopie
    gesorteer = sorted(items, key=lambda nodus: nodus["etiket"])
    return gesorteer if patroon == "reeds gesorteer" else gesorteer[::-1]


def sorteer_eksperiment(nodusse, groottes, tydgrens_s=STANDAARD_TYDGRENS_S, herhalings=5,
                        saad=1, volg=None):
    """Sorteer die nodusse (op etiket) met elke metode, op elke patroon en grootte.

    Elke ry het die tyd (mediaan/min/maks) en die presiese aantal vergelykings.
    Die resultaat word teen sorted() nagegaan; 'n verkeerde volgorde gooi 'n fout.
    """
    sleutel = lambda nodus: nodus["etiket"]
    rye = []
    for patroon in SORTEER_PATRONE:
        for naam, metode in SORTEER_METODES.items():
            def meet_een(n, metode=metode, patroon=patroon):
                items = _maak_patroon(nodusse[:n], patroon, saad)
                verwag = [x["node_id"] for x in sorted(items, key=sleutel)]
                stats, uit = meet(lambda: metode(items, sleutel), herhalings)
                if [x["node_id"] for x in uit] != verwag:
                    raise RuntimeError(f"{metode} het verkeerd gesorteer (n={n}, {patroon}).")
                vergelykings = None
                if stats["mediaan_s"] < 3.0:      # Die tel-omhulsel is stadiger; slaan dit by baie lang lopies oor.
                    TelSleutel.telling = 0
                    metode(items, lambda nodus: TelSleutel(nodus["etiket"]))
                    vergelykings = TelSleutel.telling
                return {**stats, "vergelykings": vergelykings}

            for ry in loop_leer(groottes, meet_een, tydgrens_s):
                ry = {"eksperiment": "sortering", "algoritme": naam, "patroon": patroon, **ry}
                rye.append(ry)
                if volg:
                    volg(ry)
    return rye


# ---------------------------------------------------------------------------
# Eksperiment 2: Dijkstra en A* met verskillende toue
# ---------------------------------------------------------------------------

def kies_pare(graf, aantal, saad=7):
    """Ewekansige (begin, doel)-pare wat bereikbaar is, saam met die korrekte tyd (heapq-Dijkstra)."""
    rng = random.Random(saad)
    ids = list(graf.nodes)
    pare = []
    pogings = 0
    while len(pare) < aantal and pogings < aantal * 50:
        pogings += 1
        begin, doel = rng.sample(ids, 2)
        verwysing = dijkstra(graf, begin, doel)
        if verwysing is not None:
            pare.append((begin, doel, verwysing.tyd_s))
    return pare


def roete_eksperiment(grawe, aantal_pare=20, tydgrens_s=STANDAARD_TYDGRENS_S, herhalings=5,
                      saad=7, volg=None):
    """Dijkstra en A* elk met drie prioriteitstoue, op dieselfde pare per grafiekgrootte.

    Een 'meting' is die tyd vir al die pare saam. Elke pad se tyd word teen die
    verwysing nagegaan, sodat ons weet al ses kombinasies is korrek.
    """
    pare_per_grootte = {n: kies_pare(graf, aantal_pare, saad) for n, graf in grawe.items()}
    rye = []
    for naam_algoritme, heuristiek in (("Dijkstra", False), ("A*", True)):
        for tou_naam, tou_klas in TOU_SOORTE.items():
            def meet_een(n, heuristiek=heuristiek, tou_klas=tou_klas):
                graf, pare = grawe[n], pare_per_grootte[n]

                def groep():
                    return [kortste_pad_met_tou(graf, b, d, tou_klas, heuristiek) for b, d, _ in pare]

                stats, uitslae = meet(groep, herhalings)
                for (b, d, verwag), uit in zip(pare, uitslae):
                    if not math.isclose(uit.tyd_s, verwag, rel_tol=1e-9):
                        raise RuntimeError(f"{naam_algoritme}/{tou_naam} het 'n verkeerde tyd gevind ({b}->{d}).")
                return {**stats, "pare": len(pare),
                        "besoek_totaal": sum(u.besoek_telling for u in uitslae),
                        "tou_werk_totaal": sum(u.tou_werk for u in uitslae)}

            for ry in loop_leer(list(grawe), meet_een, tydgrens_s):
                ry = {"eksperiment": "roete", "algoritme": naam_algoritme, "tou": tou_naam, **ry}
                rye.append(ry)
                if volg:
                    volg(ry)
    return rye


# ---------------------------------------------------------------------------
# Eksperiment 3: Kruskal met verskillende sorteermetodes
# ---------------------------------------------------------------------------

def kruskal_eksperiment(grawe, tydgrens_s=STANDAARD_TYDGRENS_S, herhalings=5, volg=None):
    """Kruskal met elke sorteermetode; wys hoeveel van die tyd in die sortering is."""
    kante_per_grootte = {n: graf.ongerigte_kante() for n, graf in grawe.items()}
    rye = []
    for naam, metode in SORTEER_METODES.items():
        def meet_een(n, metode=metode):
            graf, kante = grawe[n], kante_per_grootte[n]
            sorteer_tye = []

            def een_lopie():
                uitslag = kruskal(graf.nodes, kante, metode)
                sorteer_tye.append(uitslag.sorteer_s)
                return uitslag

            stats, uitslag = meet(een_lopie, herhalings)
            _, verwag_gewig = bereken_min_spanboom(graf.nodes, kante)   # Die bestaande Kruskal as verwysing.
            if not math.isclose(uitslag.totale_gewig, verwag_gewig, rel_tol=1e-9):
                raise RuntimeError(f"Kruskal met {naam} het 'n ander gewig as die verwysing (n={n}).")
            return {**stats, "kante": len(kante), "totale_gewig": uitslag.totale_gewig,
                    "komponente": uitslag.aantal_komponente,
                    "sorteer_mediaan_s": statistics.median(sorteer_tye[-stats["herhalings"]:])}

        for ry in loop_leer(list(grawe), meet_een, tydgrens_s):
            ry = {"eksperiment": "kruskal", "algoritme": f"Kruskal + {naam}", **ry}
            rye.append(ry)
            if volg:
                volg(ry)
    return rye
