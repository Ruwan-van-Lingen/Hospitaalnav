"""Dijkstra en A* met verwisselbare prioriteitstoue, om te wys hoe die keuse van datastruktuur skaal.

Die hoofprojek gebruik heapq (binêre hoop). Hier vergelyk ons dit met twee
swakker keuses, op dieselfde grafiek en dieselfde pare:

  • HoopTou          - heapq: push en pop is O(log n).
  • WoordeboekTou    - 'n woordeboek (hash table) van oop nodusse; die kleinste
                       word met min() gesoek, dus O(n) per pop en O(V²) in totaal.
  • SorteerLysTou    - 'n lys wat gesorteer gehou word met bisect; pop is O(1),
                       maar elke insetting skuif elemente (O(n) per push).

Elke tou tel sy eie 'werk' (tou_werk), sodat ons kan wys WAAR die tyd heen gaan:
  hoop: push + pop; woordeboek: push + elke item wat min() moes besigtig;
  gesorteerde lys: pop + elke element wat by 'n insetting verskuif is.
Dié telling is dieselfde elke keer, anders as sekondes.
"""

import bisect
import heapq
import math
import time
from dataclasses import dataclass


class HoopTou:
    naam = "Binêre hoop (heapq)"

    def __init__(self):
        self.lys = []
        self.werk = 0

    def push(self, f, g, nodus):
        heapq.heappush(self.lys, (f, g, nodus))
        self.werk += 1

    def pop(self):
        self.werk += 1
        return heapq.heappop(self.lys)

    def __bool__(self):
        return bool(self.lys)


class WoordeboekTou:
    naam = "Woordeboek + min()-skandering"

    def __init__(self):
        # nodus -> (f, g). 'n Nuwe push vervang die ou waarde (decrease-key), dus geen duplikate nie.
        self.inskrywings = {}
        self.werk = 0

    def push(self, f, g, nodus):
        self.inskrywings[nodus] = (f, g)
        self.werk += 1

    def pop(self):
        # min() moet elke oop nodus besigtig; dit is die bottelnek van hierdie variant.
        self.werk += len(self.inskrywings)
        nodus = min(self.inskrywings, key=self.inskrywings.get)
        f, g = self.inskrywings.pop(nodus)
        return f, g, nodus

    def __bool__(self):
        return bool(self.inskrywings)


class SorteerLysTou:
    naam = "Gesorteerde lys (bisect)"

    def __init__(self):
        # Stygend op (-f, -g): die kleinste f staan heel agter, sodat pop() O(1) is.
        self.lys = []
        self.werk = 0

    def push(self, f, g, nodus):
        item = (-f, -g, nodus)
        posisie = bisect.bisect_left(self.lys, item)
        self.werk += len(self.lys) - posisie + 1   # Elemente wat regs van die gaping moet skuif.
        self.lys.insert(posisie, item)

    def pop(self):
        self.werk += 1
        negatief_f, negatief_g, nodus = self.lys.pop()
        return -negatief_f, -negatief_g, nodus

    def __bool__(self):
        return bool(self.lys)


TOU_SOORTE = {
    HoopTou.naam: HoopTou,
    WoordeboekTou.naam: WoordeboekTou,
    SorteerLysTou.naam: SorteerLysTou,
}


@dataclass
class TouUitslag:
    pad: list[str]
    tyd_s: float
    besoek_telling: int   # Nodusse uitgebrei (dieselfde vir elke tou, behalwe by gelyke f-waardes).
    tou_werk: int         # Sien die module-beskrywing; wys waar die tyd heen gaan.
    duur_s: float


def kortste_pad_met_tou(graf, begin, doel, tou_klas, gebruik_heuristiek, geblokkeer=None):
    """Dieselfde lus as groot_algoritmes._kortste_pad, maar met 'n verwisselbare tou.

    Gee None as geen pad bestaan nie. gebruik_heuristiek=False is Dijkstra,
    True is A*. Die heuristiek kom van die grafiek self (graf.heuristiek).
    """
    if begin not in graf.nodes or doel not in graf.nodes:
        raise ValueError("Begin- of doelnodus nie in die grafiek gevind nie.")
    geblokkeer = geblokkeer or set()
    if begin in geblokkeer or doel in geblokkeer:
        return None

    begin_klok = time.perf_counter()
    h = graf.heuristiek if gebruik_heuristiek else (lambda a, b: 0.0)
    tou = tou_klas()
    tou.push(h(begin, doel), 0.0, begin)
    g_score = {begin: 0.0}
    kom_van: dict[str, str] = {}
    besoek: set[str] = set()

    while tou:
        _, g, huidig = tou.pop()
        if huidig in besoek:
            continue  # Verouderde inskrywing (kom net by die hoop en die gesorteerde lys voor).
        besoek.add(huidig)

        if huidig == doel:
            pad = [huidig]
            while pad[-1] in kom_van:
                pad.append(kom_van[pad[-1]])
            pad.reverse()
            return TouUitslag(pad, g, len(besoek), tou.werk, time.perf_counter() - begin_klok)

        for rand in graf.adjacency[huidig]:
            buur = rand.na_node
            if buur in geblokkeer:
                continue
            nuwe_g = g + rand.gewig_s
            if nuwe_g < g_score.get(buur, math.inf):
                g_score[buur] = nuwe_g
                kom_van[buur] = huidig
                tou.push(nuwe_g + h(buur, doel), nuwe_g, buur)
    return None
