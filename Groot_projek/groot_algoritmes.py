"""Algoritmes vir die groot-datastel-vertoning (los van die hoofprojek).

Die lektor wil die algoritmes op ongeveer 2000 datapunte sien, sodat
bottelnekke en tydsverskille duidelik word. Hierdie lêer is 'n byvoeging:
geen bestaande lêer word verander nie.

Wat hier leef
-------------
  • GrootGrafiek   - 'n ligte grafiek in geheue (geen SQLite nodig nie).
  • dijkstra/astar - dieselfde roetevraag, maar met 'n teller vir hoeveel
                     nodusse uitgebrei is. Só kan ons A* en Dijkstra regverdig
                     vergelyk, ook op 'n stadiger of vinniger rekenaar.
  • bereken_ontruimingskaart - omgekeerde multibron-Dijkstra, een keer vir
                     ALLE nodusse (nie net een beginpunt nie).
  • kruskal        - Kruskal waarin die sorteermetode 'n parameter is,
                     sodat ons kan wys hoe invoeg- en saamsmeltsortering die
                     spanboom beïnvloed.
  • maks_vloei_na_uitgange - Edmonds-Karp met 'n superbron (bv. 'n hele vloer)
                     en 'n superput (alle nooduitgange).

Die sortering (Sorteer.py), UnionFind en Edmonds-Karp (mst_en_vloei.py) word
net ingevoer; die bestaande kode bly presies soos dit is.
"""

import heapq
import math
import time
from dataclasses import dataclass

# Dieselfde konstantes as die hoofprojek, sodat die metriek en kapasiteite
# nooit stilweg verskil van wat in die res van die stelsel gebruik word nie.
from HospitaalGrafiek import VERSTEK_KAPASITEIT, VLOER_VERANDER_PENALTY_S
from mst_en_vloei import UnionFind, edmonds_karp
from Sorteer import insertion_sort, merge_sort

# Name vir die kunsmatige bron en put in die vloeinetwerk. Tekste eerder as
# object(), sodat gesorteerde uitvoer nooit op 'n TypeError kan afskop nie.
SUPER_BRON = "__SUPER_BRON__"
SUPER_PUT = "__SUPER_PUT__"


# ---------------------------------------------------------------------------
# Die grafiek
# ---------------------------------------------------------------------------

@dataclass
class GrootRand:
    """Een uitgaande verbinding vanaf 'n nodus."""
    na_node: str
    gewig_s: float      # Totale reistyd (basis + wag) in sekondes.
    afstand_m: float    # Loopafstand; 0 vir trappe en hysbakke.
    kapasiteit: float   # Persone per sekonde (demonstrasiewaarde).
    rand_tipe: str      # 'GANG', 'TRAPPE', 'HUISBAK', 'LUGBRUG', 'TONNEL'


class GrootGrafiek:
    """Gerigte, geweegde grafiek in geheue, met dieselfde reëls as die hoofprojek."""

    def __init__(self):
        # node_id -> {"node_id", "etiket", "vloer", "pos", "tipe_kode", "is_nooduitgang"}
        self.nodes: dict[str, dict] = {}
        # node_id -> lys uitgaande rande (tweerigtingrande staan in albei nodusse se lyste).
        self.adjacency: dict[str, list[GrootRand]] = {}
        # Elke rand presies soos dit ingevoer is; Kruskal en die CSV-uitvoer gebruik dit.
        self.rande_lys: list[tuple] = []
        # None beteken "moet herbereken word" (sien heuristiek_skaal_kry()).
        self._heuristiek_skaal: float | None = None

    # -- opbou ---------------------------------------------------------------

    def voeg_nodus_by(self, node_id, etiket, vloer, pos_x, pos_y,
                      tipe_kode="DEPARTEMENT", is_nooduitgang=False):
        """Voeg een nodus by; 'vloer' is die vloervlak as heelgetal (0 = grondvloer)."""
        if node_id in self.nodes:
            raise ValueError(f"Nodus '{node_id}' bestaan reeds.")
        self.nodes[node_id] = {
            "node_id": node_id,
            "etiket": etiket,
            "vloer": int(vloer),
            "pos": (float(pos_x), float(pos_y)),
            "tipe_kode": tipe_kode,
            "is_nooduitgang": bool(is_nooduitgang),
        }
        self.adjacency[node_id] = []

    def voeg_rand_by(self, van, na, rand_tipe, afstand_m, gewig_s,
                     kapasiteit=VERSTEK_KAPASITEIT, bidirectional=True):
        """Voeg 'n rand by (en sy omgekeerde as bidirectional waar is)."""
        if van not in self.nodes or na not in self.nodes:
            raise ValueError(f"Rand {van} -> {na} verwys na 'n onbekende nodus.")
        # Dieselfde reël as Rand in HospitaalGrafiek.py: eindig en nie-negatief.
        for naam, waarde in (("afstand_m", afstand_m), ("gewig_s", gewig_s),
                             ("kapasiteit", kapasiteit)):
            if not math.isfinite(waarde) or waarde < 0:
                raise ValueError(f"{naam} moet eindig en nie-negatief wees (rand {van} -> {na}).")
        self.rande_lys.append((van, na, rand_tipe, afstand_m, gewig_s, kapasiteit, bool(bidirectional)))
        self.adjacency[van].append(GrootRand(na, gewig_s, afstand_m, kapasiteit, rand_tipe))
        if bidirectional:
            self.adjacency[na].append(GrootRand(van, gewig_s, afstand_m, kapasiteit, rand_tipe))
        self._heuristiek_skaal = None  # 'n Nuwe rand kan die skaal verander.

    # -- hulpmiddels vir A* ----------------------------------------------------

    def metriek(self, a: str, b: str) -> float:
        """Koördinaatafstand plus 'n straf per vloerverskil (soos HospitaalGrafiek._metriek)."""
        (ax, ay), (bx, by) = self.nodes[a]["pos"], self.nodes[b]["pos"]
        vloer_delta = abs(self.nodes[a]["vloer"] - self.nodes[b]["vloer"])
        return math.hypot(ax - bx, ay - by) + vloer_delta * VLOER_VERANDER_PENALTY_S

    def heuristiek_skaal_kry(self) -> float:
        """Kleinste verhouding randtyd / randmetriek; hou die A*-skatting 'n geldige ondergrens."""
        if self._heuristiek_skaal is None:
            verhoudings = []
            for van, rande in self.adjacency.items():
                for rand in rande:
                    afstand = self.metriek(van, rand.na_node)
                    if afstand > 0:
                        verhoudings.append(rand.gewig_s / afstand)
            self._heuristiek_skaal = min(verhoudings, default=0.0)
        return self._heuristiek_skaal

    def heuristiek(self, a: str, b: str) -> float:
        """Onderste grens vir die oorblywende reistyd in sekondes."""
        return self.heuristiek_skaal_kry() * self.metriek(a, b)

    # -- afgeleide lyste -------------------------------------------------------

    def nooduitgange(self, geblokkeer=None) -> list[str]:
        """Alle nooduitgange wat nie geblokkeer is nie."""
        geblokkeer = geblokkeer or set()
        return [n for n, data in self.nodes.items()
                if data["is_nooduitgang"] and n not in geblokkeer]

    def ongerigte_kante(self) -> list[tuple[str, str, float]]:
        """Goedkoopste rand per noduspaar, ongerig (invoer vir Kruskal)."""
        kante_per_paar: dict[tuple[str, str], float] = {}
        for van, rande in self.adjacency.items():
            for rand in rande:
                if van == rand.na_node:
                    continue  # Selflusse dra niks by tot 'n spanboom nie.
                sleutel = (van, rand.na_node) if van < rand.na_node else (rand.na_node, van)
                kante_per_paar[sleutel] = min(kante_per_paar.get(sleutel, math.inf), rand.gewig_s)
        return [(a, b, gewig) for (a, b), gewig in kante_per_paar.items()]


# ---------------------------------------------------------------------------
# Kortste pad: Dijkstra en A* deel een funksie
# ---------------------------------------------------------------------------

@dataclass
class RoeteUitslag:
    pad: list[str]
    tyd_s: float
    afstand_m: float
    besoek_telling: int   # Nodusse wat uit die hoop gehaal en uitgebrei is (die regverdige vergelykingsmaat).
    duur_s: float         # Werklike rekentyd; hang van die rekenaar af.


def _kortste_pad(graf, begin, doel, gebruik_heuristiek, geblokkeer):
    """Deel die lus van Dijkstra en A*; die enigste verskil is die heuristiek.

    Met h = 0 is f gelyk aan g en is dit Dijkstra. Met die geskaalde metriek
    sorteer A* die hoop eerder na nodusse wat naby die doel lê, sodat dit
    gewoonlik minder nodusse uitbrei. Albei vind dieselfde minimum tyd.
    """
    if begin not in graf.nodes or doel not in graf.nodes:
        raise ValueError("Begin- of doelnodus nie in die grafiek gevind nie.")
    geblokkeer = geblokkeer or set()
    if begin in geblokkeer or doel in geblokkeer:
        return None

    begin_klok = time.perf_counter()
    h = graf.heuristiek if gebruik_heuristiek else (lambda a, b: 0.0)

    hoop = [(h(begin, doel), 0.0, begin)]       # (f, g, nodus)
    g_score = {begin: 0.0}
    afstand_score = {begin: 0.0}
    kom_van: dict[str, str] = {}
    besoek: set[str] = set()

    while hoop:
        _, g, huidig = heapq.heappop(hoop)
        if huidig in besoek:
            continue  # Verouderde hoop-inskrywing.
        besoek.add(huidig)

        if huidig == doel:
            pad = [huidig]
            while pad[-1] in kom_van:
                pad.append(kom_van[pad[-1]])
            pad.reverse()
            return RoeteUitslag(pad, g, afstand_score[huidig], len(besoek),
                                time.perf_counter() - begin_klok)

        for rand in graf.adjacency[huidig]:
            buur = rand.na_node
            if buur in geblokkeer:
                continue
            nuwe_g = g + rand.gewig_s
            if nuwe_g < g_score.get(buur, math.inf):
                g_score[buur] = nuwe_g
                afstand_score[buur] = afstand_score[huidig] + rand.afstand_m
                kom_van[buur] = huidig
                heapq.heappush(hoop, (nuwe_g + h(buur, doel), nuwe_g, buur))
    return None  # Geen pad bestaan nie.


def dijkstra(graf, begin, doel, geblokkeer=None):
    """Kortste pad sonder heuristiek; die verwysing waarteen A* gemeet word."""
    return _kortste_pad(graf, begin, doel, False, geblokkeer)


def astar(graf, begin, doel, geblokkeer=None):
    """Kortste pad met die geskaalde metriek as heuristiek."""
    return _kortste_pad(graf, begin, doel, True, geblokkeer)


# ---------------------------------------------------------------------------
# Ontruiming: omgekeerde multibron-Dijkstra vir alle nodusse
# ---------------------------------------------------------------------------

@dataclass
class OntruimingsKaart:
    tyd_s: dict[str, float]      # node_id -> tyd na die naaste uitgang (net bereikbare nodusse).
    volgende: dict[str, str]     # node_id -> die volgende nodus op pad na daardie uitgang.
    duur_s: float

    def pad(self, begin: str):
        """Volg die 'volgende'-wysers tot by die uitgang; None as begin nie bereikbaar is nie."""
        if begin not in self.tyd_s:
            return None
        pad = [begin]
        while pad[-1] in self.volgende:
            pad.append(self.volgende[pad[-1]])
        return pad


def bereken_ontruimingskaart(graf, geblokkeer=None) -> OntruimingsKaart:
    """Een Dijkstra-deurloop vanaf alle uitgange gee elke nodus se ontruimingstyd.

    Die hoofprojek doen dit vir een beginpunt op 'n slag. Vir 2000 nodusse is
    een deurloop vir almal veel goedkoper as 2000 aparte soektogte
    (O(E log V) in totaal in plaas van O(V · E log V)). Hysbakke word
    uitgesluit, soos in die hoofprojek.
    """
    geblokkeer = geblokkeer or set()
    begin_klok = time.perf_counter()

    # Omgekeerde aangrensing: vir 'n rand van -> na kry 'na' 'n inskrywing wat terug na 'van' wys.
    omgekeerd: dict[str, list[tuple[str, float]]] = {n: [] for n in graf.nodes}
    for van, rande in graf.adjacency.items():
        for rand in rande:
            if rand.rand_tipe != "HUISBAK":
                omgekeerd[rand.na_node].append((van, rand.gewig_s))

    tyd_s: dict[str, float] = {}
    volgende: dict[str, str] = {}
    hoop: list[tuple[float, str]] = []
    for uitgang in graf.nooduitgange(geblokkeer):
        tyd_s[uitgang] = 0.0
        heapq.heappush(hoop, (0.0, uitgang))

    klaar: set[str] = set()
    while hoop:
        koste, huidig = heapq.heappop(hoop)
        if huidig in klaar:
            continue
        klaar.add(huidig)
        for buur, gewig in omgekeerd[huidig]:
            if buur in geblokkeer:
                continue
            nuwe = koste + gewig
            if nuwe < tyd_s.get(buur, math.inf):
                tyd_s[buur] = nuwe
                volgende[buur] = huidig
                heapq.heappush(hoop, (nuwe, buur))

    return OntruimingsKaart(tyd_s, volgende, time.perf_counter() - begin_klok)


# ---------------------------------------------------------------------------
# Kruskal met 'n verwisselbare sorteermetode
# ---------------------------------------------------------------------------

@dataclass
class KruskalUitslag:
    kante: list[tuple[str, str, float]]
    totale_gewig: float
    aantal_komponente: int   # 1 = verbind; meer as 1 = 'n spanwoud.
    sorteer_s: float         # Tyd net vir die sorteerstap.
    totaal_s: float          # Sortering + Union-Find.


def kruskal(nodusse, kante, sorteer=merge_sort) -> KruskalUitslag:
    """Kruskal: sorteer rande volgens gewig en neem elkeen wat geen siklus vorm nie.

    nodusse : lys node-ID's.
    kante   : lys (a, b, gewig).
    sorteer : funksie(items, sleutel) soos insertion_sort of merge_sort. Die
              sortering is die duur stap (O(E log E) of O(E²)); Union-Find
              ná die sortering is byna lineêr. Daarom wys ons hoe die
              keuse van sorteermetode Kruskal se spoed bepaal.
    """
    nodusse = list(nodusse)
    uf = UnionFind(nodusse)
    totaal_begin = time.perf_counter()

    sorteer_begin = time.perf_counter()
    gesorteer = sorteer(kante, lambda kant: kant[2])
    sorteer_s = time.perf_counter() - sorteer_begin

    mst_kante = []
    totale_gewig = 0.0
    for a, b, gewig in gesorteer:
        if uf.unie(a, b):          # Gee False as dit 'n siklus sou vorm.
            mst_kante.append((a, b, gewig))
            totale_gewig += gewig
            if len(mst_kante) == len(nodusse) - 1:
                break              # Volledige spanboom: die res van die rande is oortollig.

    return KruskalUitslag(
        mst_kante, totale_gewig, len(nodusse) - len(mst_kante),
        sorteer_s, time.perf_counter() - totaal_begin,
    )


# Die drie sorteermetodes wat vergelyk word. Die derde is Python se eie
# sorted() en dien net as verwysingslyn; dit is nie deel van die projek se
# handgeskrewe algoritmes nie.
SORTEER_METODES = {
    "Invoegsortering": insertion_sort,
    "Saamsmeltsortering": merge_sort,
    "Python sorted() (verwysing)": lambda items, sleutel=None: sorted(items, key=sleutel),
}


# ---------------------------------------------------------------------------
# Maksimum vloei met 'n superbron en 'n superput
# ---------------------------------------------------------------------------

@dataclass
class VloeiUitslag:
    maks_vloei: float                          # Persone per sekonde.
    bottelnekke: list[tuple[str, str, float]]  # Min-snit-rande (van, na, kapasiteit).
    aantal_bronne: int
    duur_s: float


def maks_vloei_na_uitgange(graf, bronne, geblokkeer=None):
    """Maksimum deurvloei van 'n GROEP bronne (bv. 'n hele vloer) na alle uitgange.

    Een bron het net 'n paar rande en word dus altyd net deur sy eie
    deur beperk. Met 'n hele vloer as bron verskyn die ware bottelnekke
    (trappe en nou gange) soos in 'n werklike ontruiming. Hysbakke word
    uitgesluit. Gee None as daar geen bron of uitgang oor is nie.
    """
    geblokkeer = geblokkeer or set()
    begin_klok = time.perf_counter()

    uitgange = graf.nooduitgange(geblokkeer)
    uitgang_stel = set(uitgange)
    # 'n Bron wat self 'n uitgang is, hoef nêrens heen te loop nie.
    bronne = [b for b in bronne if b not in geblokkeer and b not in uitgang_stel]
    if not bronne or not uitgange:
        return None

    kante = [
        (van, rand.na_node, rand.kapasiteit)
        for van, rande in graf.adjacency.items() if van not in geblokkeer
        for rand in rande
        if rand.rand_tipe != "HUISBAK" and rand.na_node not in geblokkeer
    ]
    # Groter as enige moontlike vloei, sodat die kunsmatige rande nooit self 'n bottelnek word nie.
    groot = sum(kap for _, _, kap in kante) + 1.0
    kante += [(SUPER_BRON, b, groot) for b in bronne]
    kante += [(u, SUPER_PUT, groot) for u in uitgange]

    vloei, snit = edmonds_karp(kante, SUPER_BRON, SUPER_PUT)
    bottelnekke = sorted(
        ((a, b, k) for a, b, k in snit if a != SUPER_BRON and b != SUPER_PUT),
        key=lambda kant: (kant[0], kant[1]),
    )
    return VloeiUitslag(float(vloei), bottelnekke, len(bronne), time.perf_counter() - begin_klok)
