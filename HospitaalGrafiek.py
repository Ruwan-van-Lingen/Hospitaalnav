"""Grafieklaaier en netwerkalgoritmes vir die hospitaalnavigasiestelsel.

A* vind die tyd-optimale toegelate pad. Die heuristiek is 'n metriek van
koördinate en vloervlakke, geskaal volgens die kleinste verhouding tussen
randtyd en randmetriek. Só bly die skatting 'n geldige onderste tydgrens;
'n vaste vloerstraf sonder dié skaling sou nie korrektheid waarborg nie.

Ontruiming gebruik omgekeerde multibron-Dijkstra vanaf alle toegelate
nooduitgange. Slegs werklike randrigtings word gevolg en hysbakke word
uitgesluit. Kruskal ontleed die ongerigte infrastruktuur; Edmonds-Karp
bereken gemodelleerde maksimum vloei. Beide algoritmes is in mst_en_vloei.py
geskryf; hierdie lêer stel net hul invoer saam. Geen van hierdie demonstrasies
vervang 'n professioneel goedgekeurde ontruimingsplan nie.
"""

import os
import sqlite3
import math
import heapq
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
from dataclasses import dataclass
from typing import Optional
from Boom24 import Boom24
# Kruskal en Edmonds-Karp leef in een lêer; hierdie klas voeg net die
# hospitaalreëls (toegang, sluitings, nooduitgange) by die invoer.
from mst_en_vloei import bereken_min_spanboom as kruskal_spanboom, edmonds_karp

# Skaal vir vloerverskille in die meetkundige metriek. Die metriek word
# daarna volgens werklike randtye geskaal; 20 is dus nie 'n reistydwaarborg nie.
VLOER_VERANDER_PENALTY_S = 20.0
VERSTEK_KAPASITEIT = 4.0  # Demonstrasiewaarde in persone per sekonde.

# Afstand/gewigsfunksies
# ----------------------
# Die projekvereiste vra uitdruklik dat lambda-funksies gebruik word. Hierdie
# twee benoemde lambda's hou die formules op een plek en word deur die werklike
# grafieklaai- en A*-kode hieronder gebruik.
BEREKEN_AFSTAND = lambda pos_a, pos_b: math.hypot(  # noqa: E731
    pos_a[0] - pos_b[0], pos_a[1] - pos_b[1]
)
BEREKEN_GEWIG = lambda basis_gewig_s, wag_penalty_s: (  # noqa: E731
    float(basis_gewig_s) + float(wag_penalty_s)
)


@dataclass
class Rand:
    """Verteenwoordig 'n geweegde verbinding tussen twee nodusse in die grafiek."""
    na_node: str
    gewig_s: float      # Totale reistyd (basisgewig + wagtyd) in sekondes.
    rand_tipe: str      # Byvoorbeeld 'GANG', 'HUISBAK', 'TRAPPE', 'LUGBRUG', 'TONNEL'.
    vloer_verander: int # Aantal vloere wat hierdie rand oorsteek (0 vir horisontale rande).
    afstand_m: float    # Fisiese loopafstand in meter; 0 vir hysbakbewegings.
    kapasiteit: float = VERSTEK_KAPASITEIT

    def __post_init__(self):
        """Roete- en vloei-algoritmes vereis eindige, nie-negatiewe waardes."""
        for naam in ("gewig_s", "afstand_m", "kapasiteit"):
            waarde = getattr(self, naam)
            if not math.isfinite(waarde) or waarde < 0:
                raise ValueError(f"{naam} moet eindig en nie-negatief wees.")


class HospitaalGrafiek:
    """
    Laai die hospitaalgrafiek uit SQLite en bied roete- en netwerkanalise-
    algoritmes aan.

    Die grafiek word eenmalig by toepassingsopstart in geheue gelaai
    (via FastAPI se lifespan-hanteerder in main.py) en word dan vir alle
    versoeke hergebruik. Dit geld ook vir die toegangsregte: dit word saam
    met die nodusse en rande eenmalig gelees. 'n Verandering aan die databasis
    vereis dus 'n herbegin van die toepassing.
    """

    def __init__(self, db_pad: str):
        self.db_pad = db_pad
        # Elke node-ID word gekoppel aan sy metadata (vloer, posisie, toegangsbeperking).
        self.nodes: dict[str, dict] = {}
        # Aangrensingsstruktuur: elke node-ID word gekoppel aan sy lys uitgaande rande.
        self.adjacency: dict[str, list[Rand]] = {}
        # Elke gebruikerstipe word gekoppel aan die beperkte groepe wat hy mag betree.
        self.toegang: dict[str, set[str]] = {}
        self._load()
        self._skaal_heuristiek()

    def _load(self):
        """Laai alle nodusse en rande uit die SQLite-databasis in geheue."""
        with closing(sqlite3.connect(self.db_pad)) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Laai elke nodus saam met sy vloer- en geboumeta-inligting.
            cur.execute("""
                SELECT n.node_id, n.vloer_id, n.pos_x, n.pos_y,
                       n.beperkte_groep, n.is_nooduitgang,
                       f.level_nommer, f.gebou_id
                FROM nodes n JOIN vloere f ON n.vloer_id = f.vloer_id
            """)
            for row in cur.fetchall():
                self.nodes[row["node_id"]] = {
                    "vloer_id":       row["vloer_id"],
                    "pos":            (row["pos_x"], row["pos_y"]),
                    "level":          row["level_nommer"],
                    "gebou_id":       row["gebou_id"],
                    "beperkte_groep": row["beperkte_groep"],
                    # Sien Skema.sql: is_nooduitgang=1 vir ingange/versamelpunte buite die gebou.
                    "is_nooduitgang": bool(row["is_nooduitgang"]),
                }
                self.adjacency[row["node_id"]] = []

            # Laai alle rande en voeg ook omgekeerde rande by vir tweerigtingverbindings.
            # Ouer databasisse het dalk nog nie die kapasiteit-kolom nie. Toets daarvoor met PRAGMA table_info en
            # gebruik NULL as plekhouer, sodat dieselfde SELECT altyd werk (NULL word VERSTEK_KAPASITEIT).
            kapasiteit_kolom = "kapasiteit" in {
                ry[1] for ry in cur.execute("PRAGMA table_info(rande)")
            }
            kapasiteit_sql = "kapasiteit" if kapasiteit_kolom else "NULL AS kapasiteit"
            cur.execute(f"""
                SELECT van_node, na_node, rand_tipe, afstand_m,
                       basis_gewig_s, wag_penalty_s, vloer_verander, bidirectional,
                       {kapasiteit_sql}
                FROM rande
            """)
            for row in cur.fetchall():
                # Gebruik die sentrale lambda-gewigsfunksie vir elke rand.
                gewig = BEREKEN_GEWIG(row["basis_gewig_s"], row["wag_penalty_s"])
                kapasiteit = row["kapasiteit"]
                if kapasiteit is None:
                    kapasiteit = VERSTEK_KAPASITEIT
                e = Rand(row["na_node"], gewig, row["rand_tipe"], row["vloer_verander"], row["afstand_m"], kapasiteit)
                self.adjacency[row["van_node"]].append(e)
                if row["bidirectional"]:
                    e_rev = Rand(row["van_node"], gewig, row["rand_tipe"], row["vloer_verander"], row["afstand_m"], kapasiteit)
                    self.adjacency[row["na_node"]].append(e_rev)


            # Laai toegangsregte eenmalig, sodat toegelate_groepe() nie vir elke
            # algoritme-aanroep (of elke nodus in die dekkingskontrole) weer na
            # die databasis hoef te gaan nie. Elke tipe begin met 'n leë stel,
            # want PUBLIEK mag geen beperkte area betree nie.
            cur.execute("SELECT gebruiker_tipe FROM gebruiker_tipes")
            self.toegang = {ry[0]: set() for ry in cur.fetchall()}
            cur.execute("SELECT gebruiker_tipe, beperkte_groep FROM toegang_toestemmings")
            for tipe, groep in cur.fetchall():
                if tipe in self.toegang:
                    self.toegang[tipe].add(groep)

        # Geordende bestemmingsmetadata vir die boomsoektog.
        self.herbou_bestemmingsindeks()

    def herbou_bestemmingsindeks(self):
        """Herlaai bestemmings uit SQLite, bv. ná 'n naamverandering.

        Bou eers 'n volledige nuwe boom en vervang dan die verwysing, sodat
        lesers nie 'n gedeeltelik opgeboude indeks ontvang nie.
        """
        indeks = Boom24()
        conn = sqlite3.connect(self.db_pad)
        conn.row_factory = sqlite3.Row
        try:
            rye = conn.execute("""
                SELECT n.node_id, n.etiket, n.tipe_kode, n.beperkte_groep,
                       f.vloer_id, f.naam AS vloer_naam,
                       g.gebou_id, g.naam AS gebou_naam
                FROM nodes n
                JOIN vloere f ON n.vloer_id = f.vloer_id
                JOIN geboue g ON f.gebou_id = g.gebou_id
            """)
            for ry in rye:
                bestemming = dict(ry)
                sleutel = (bestemming["etiket"].strip().casefold(), bestemming["node_id"])
                indeks.voeg_in(sleutel, bestemming)
        finally:
            conn.close()
        self.bestemmingsindeks = indeks

    def _is_bruikbaar(self, node_id: str, toegelaat: set[str], geblokkeer: set[str]) -> bool:
        """Keur 'n nodus goed as dit nie geblokkeer of vir hierdie gebruiker beperk is nie.

        Word deur astar(), naaste_veilige_uitgang() en maks_vloei_na_uitgange()
        gedeel, sodat die toegangsreël net op een plek gewysig hoef te word.
        """
        if node_id in geblokkeer:
            return False
        groep = self.nodes[node_id]["beperkte_groep"]
        return groep is None or groep in toegelaat

    def toegelate_groepe(self, gebruiker_tipe: str) -> set[str]:
        """
        Gee die stel beperkte groepe terug wat hierdie gebruikerstipe mag betree.

        Byvoorbeeld: 'PERSONEEL' kry {'SLEGS_PERSONEEL', 'SLEGS_ICU'}, terwyl
        'PUBLIEK' 'n leë stel kry (mag geen beperkte areas betree nie).
        Gooi ValueError as die gebruikerstipe nie in die databasis bestaan nie.

        Die regte is in _load() gelees en bly in geheue, net soos die rande.
        'n Kopie word teruggegee sodat 'n aanroeper nie per ongeluk die
        gestoorde stel kan verander nie.
        """
        if gebruiker_tipe not in self.toegang:
            raise ValueError(f"Ongeldige gebruikerstipe: {gebruiker_tipe}")
        return set(self.toegang[gebruiker_tipe])

    def soek_bestemmings(self, soekterm: str = "", limiet: int = 20) -> list[dict]:
        """
        Soek naam, node-ID, tipe, gebou en vloer in die 2-4-boom se metadata.

        Gebruik deur die /destinations eindpunt in main.py sodat die webkoppelvlak
        mensleesbare etikette (met gebou- en vloerinligting) kan vertoon sonder
        dat die gebruiker rou node-ID's hoef te ken.
        """
        # Kopieë beskerm die indeks se metadata teen verandering deur 'n leser.
        return [dict(item) for item in
                self.bestemmingsindeks.soek_metadata(soekterm, limiet)]

    def _metriek(self, a: str, b: str) -> float:
        """Meet koördinaatafstand en vloerverskil in dieselfde metriek."""
        planar = BEREKEN_AFSTAND(self.nodes[a]["pos"], self.nodes[b]["pos"])
        vloer_delta = abs(self.nodes[a]["level"] - self.nodes[b]["level"])
        return planar + vloer_delta * VLOER_VERANDER_PENALTY_S

    def _skaal_heuristiek(self) -> None:
        """Kies die kleinste verhouding tussen randtyd en metrieke afstand.

        Vir elke rand u→v geld skaal*d(u,v) <= reistyd(u,v). Saam met
        die driehoeksongelykheid maak dit h(n)=skaal*d(n,doel) konsekwent
        en toelaatbaar. 'n Kostelose rand kan die skaal tot nul verlaag;
        A* werk dan soos Dijkstra. Geen meter word direk by sekondes getel nie.
        """
        verhoudings = []
        for van, rande in self.adjacency.items():
            for rand in rande:
                afstand = self._metriek(van, rand.na_node)
                if afstand > 0:
                    verhoudings.append(rand.gewig_s / afstand)
        self.heuristiek_skaal = min(verhoudings, default=0.0)

    def _heuristic(self, a: str, b: str) -> float:
        """Gee 'n onderste grens vir oorblywende reistyd in sekondes."""
        return self.heuristiek_skaal * self._metriek(a, b)

    def astar(
        self,
        begin: str,
        doel: str,
        gebruiker_tipe: str = "PUBLIEK",
        geblokkeerde_nodes: Optional[set[str]] = None,
    ) -> Optional[tuple[list[str], float, float]]:
        """
        Vind die tyd-optimale roete van 'begin' na 'doel' met die A*-algoritme.

        Gee 'n tuple (pad, tyd_sekondes, afstand_m) terug, of None as geen
        toegelate pad bestaan nie.

        Parameters
        ----------
        begin              : Beginnode se ID.
        doel               : Doelnode se ID.
        gebruiker_tipe     : Bepaal watter beperkte nodusse betree mag word.
        geblokkeerde_nodes : Stel node-ID's wat weens 'n aktiewe insident
                             tydelik ongeskik is (A* sal hulle omseil).

        Afstand
        -------
        Die teruggegee afstand is die som van afstand_m langs die tyd-optimale
        pad. Hysbakrande dra niks by nie (afstand_m = 0) aangesien hulle geen
        fisiese loopafstand verteenwoordig nie.
        """
        if begin not in self.nodes or doel not in self.nodes:
            raise ValueError("Begin- of doelnodus nie in die grafiek gevind nie.")

        toegelaat = self.toegelate_groepe(gebruiker_tipe)
        geblokkeer = geblokkeerde_nodes or set()

        # Kyk vroeg of begin of doel self ontoeganklik is.
        if not (self._is_bruikbaar(begin, toegelaat, geblokkeer)
                and self._is_bruikbaar(doel, toegelaat, geblokkeer)):
            return None

        # Hoop-inskrywing: (f_score, g_score, node_id)
        open_set = [(self._heuristic(begin, doel), 0.0, begin)]
        kom_van: dict[str, str] = {}
        g_score = {begin: 0.0}
        afstand_score = {begin: 0.0}  # Kumulatiewe loopafstand langs die tyd-optimale pad.
        besoek: set[str] = set()

        while open_set:
            _, koste_so_ver, huidig = heapq.heappop(open_set)

            if huidig == doel:
                # Doel bereik — herstel die pad van doel terug na begin.
                return self._reconstruct(kom_van, huidig), koste_so_ver, afstand_score[huidig]

            if huidig in besoek:
                continue  # Verouderde hoop-inskrywing — sla oor.
            besoek.add(huidig)

            for rand in self.adjacency[huidig]:
                if not self._is_bruikbaar(rand.na_node, toegelaat, geblokkeer):
                    continue  # Ontoeganklik vir hierdie gebruikerstipe of tydelik geblokkeer.
                tentatiewe_g = koste_so_ver + rand.gewig_s
                if tentatiewe_g < g_score.get(rand.na_node, math.inf):
                    g_score[rand.na_node] = tentatiewe_g
                    afstand_score[rand.na_node] = afstand_score[huidig] + rand.afstand_m
                    kom_van[rand.na_node] = huidig
                    f_score = tentatiewe_g + self._heuristic(rand.na_node, doel)
                    heapq.heappush(open_set, (f_score, tentatiewe_g, rand.na_node))

        return None  # Geen toegelate pad gevind nie.

    def naaste_veilige_uitgang(
        self,
        begin: str,
        gebruiker_tipe: str = "PUBLIEK",
        geblokkeerde_nodes: Optional[set[str]] = None,
    ) -> Optional[tuple[list[str], float, float]]:
        """
        Ontruimingsmodus: vind die tyd-optimale pad na die naaste nooduitgang.

        Waarom Multi-bron Omgekeerde Dijkstra?
        ----------------------------------------
        Tydens ontruiming is die teiken nie 'n enkele bekende bestemming nie,
        maar die NAASTE van verskeie moontlike nooduitgange. Die naïewe
        benadering — voer A* 'n keer per uitgang uit en kies die kortste —
        sou O(U × E log V) kos (U = aantal uitgange). Multi-bron Dijkstra
        bereik dieselfde resultaat in 'n enkele O(E log V) deurgang:

          1. Laai ALLE geldige nooduitgange gelyktydig in die Dijkstra-hoop,
             elk met koste 0.
          2. Dijkstra brei omgekeerd uit deur die omgekeerde aangrensings-
             struktuur (d.i. elke rand word in die teenoorgestelde rigting
             gestap) totdat die beginpunt bereik word.
          3. Die eerste keer dat 'begin' uitgehaal word uit die hoop is dit
             gewaarborg die goedkoopste pad na die naaste uitgang.

        Die omgekeerde aangrensingsstruktuur en omgekeerde herstelpad
        lewer 'n roete van begin tot uitgang in die oorspronklike randrigting.

        Hysbakrande (rand_tipe='HUISBAK') word in hierdie model uitgelaat;
        gewone gange, trappe, lugbrûe en tonnels bly beskikbaar.

        Gee None terug as geen bereikbare nooduitgang bestaan nie.
        """
        if begin not in self.nodes:
            raise ValueError(f"Beginpunt '{begin}' nie gevind in grafiek nie.")

        toegelaat = self.toegelate_groepe(gebruiker_tipe)
        geblokkeer = geblokkeerde_nodes or set()

        if not self._is_bruikbaar(begin, toegelaat, geblokkeer):
            return None

        # --- Bou die omgekeerde aangrensingsstruktuur ---
        # In die gewone aangrensingslys wys 'A → B'. Hier wys 'B → A',
        # sodat Dijkstra kan "terugloop" van uitgange na die beginpunt.
        omgekeerde: dict[str, list[Rand]] = {nid: [] for nid in self.nodes}
        for van_node, rande in self.adjacency.items():
            for rand in rande:
                # Brandveiligheidsreël: geen hysbakke tydens ontruiming.
                if rand.rand_tipe == "HUISBAK":
                    continue
                # Voeg omgekeerde rigting by (uitgang → begin soekrigting).
                omgekeerde[rand.na_node].append(
                    Rand(van_node, rand.gewig_s, rand.rand_tipe, rand.vloer_verander, rand.afstand_m)
                )
                # Tweerigtingverbindings is reeds afsonderlike rande in
                # adjacency. Voeg hier slegs die omgekeerde van elke rand by.

        # --- Multibron Dijkstra ---
        # Laai alle bereikbare nooduitgange as beginpunte met koste 0.
        g_score: dict[str, float] = {}
        afstand_score: dict[str, float] = {}
        kom_van: dict[str, str] = {}
        hoop: list[tuple[float, str]] = []  # (koste, node_id)

        for nid, data in self.nodes.items():
            if data["is_nooduitgang"] and self._is_bruikbaar(nid, toegelaat, geblokkeer):
                g_score[nid] = 0.0
                afstand_score[nid] = 0.0
                heapq.heappush(hoop, (0.0, nid))

        if not hoop:
            return None  # Geen nooduitgange beskikbaar of almal geblokkeer.

        besoek: set[str] = set()

        while hoop:
            koste_so_ver, huidig = heapq.heappop(hoop)

            if huidig == begin:
                # Beginpunt gevind — dit is die optimale pad na die naaste uitgang.
                # _reconstruct volg kom_van van 'begin' terug na die uitgang en
                # keer die lys om, sodat die finale pad lees as [begin, ..., uitgang].
                pad = self._reconstruct(kom_van, begin)
                pad.reverse()
                return pad, koste_so_ver, afstand_score[begin]

            if huidig in besoek:
                continue
            besoek.add(huidig)

            for rand in omgekeerde[huidig]:
                bure = rand.na_node
                if not self._is_bruikbaar(bure, toegelaat, geblokkeer):
                    continue
                tentatiewe_g = koste_so_ver + rand.gewig_s
                if tentatiewe_g < g_score.get(bure, math.inf):
                    g_score[bure] = tentatiewe_g
                    afstand_score[bure] = afstand_score[huidig] + rand.afstand_m
                    kom_van[bure] = huidig
                    heapq.heappush(hoop, (tentatiewe_g, bure))

        return None  # Geen bereikbare nooduitgang gevind nie.

    def bereken_min_spanboom(self) -> tuple[list[tuple[str, str, float]], float]:
        """
        Bereken die minimum spanboom (MST) van die hele hospitaalgrafiek met
        Kruskal se algoritme, met gewig_s (dieselfde koste-eenheid as A*) as
        randgewig. Eenrigtingrande word vir hierdie ontleding as ongerig
        behandel; 'n ontkoppelde grafiek lewer 'n minimum spanwoud.

        LET WEL: dit is 'n ANDER vraag as astar()/naaste_veilige_uitgang().
        Dit vind NIE die kortste pad tussen twee spesifieke punte nie — dit
        vind die goedkoopste stel korridors wat AL die nodusse in die
        hospitaal aan mekaar verbind, sonder oortollige verbindings. Nuttig
        vir infrastruktuur-analise (bv. "wat is die minimum netwerk wat die
        hele gebou bereikbaar hou?"), nie vir gebruikersnavigasie nie.

        Gee (mst_kante, totale_gewig) terug, waar mst_kante 'n lys
        (van_node, na_node, gewig_s) tuples is wat die MST vorm.
        """
        # Ontleed die ongerigte infrastruktuur; behou die goedkoopste rand
        # per noduspaar, ook wanneer teenoorgestelde rigtings verskil.
        kante_per_paar = {}
        for van_node, rande in self.adjacency.items():
            for rand in rande:
                if van_node == rand.na_node:
                    continue
                sleutel = tuple(sorted((van_node, rand.na_node)))
                kante_per_paar[sleutel] = min(
                    kante_per_paar.get(sleutel, math.inf), rand.gewig_s
                )
        kante = [(a, b, gewig) for (a, b), gewig in kante_per_paar.items()]

        # Kruskal self (sortering + Union-Find) leef in mst_en_vloei.py.
        return kruskal_spanboom(self.nodes, kante)

    def maks_vloei_na_uitgange(
        self,
        bron: str,
        gebruiker_tipe: str = "PUBLIEK",
        geblokkeerde_nodes: Optional[set[str]] = None,
    ) -> Optional[tuple[float, list[tuple[str, str, float]]]]:
        """
        Bereken die maksimum deurvloei van 'bron' na AL die nooduitgange
        gelyktydig, met Edmonds-Karp (BFS-gebaseerde Ford-Fulkerson).

        In teenstelling met naaste_veilige_uitgang() (kortste TYD na een
        uitgang), beantwoord hierdie metode: "as almal gelyktydig ontruim,
        hoeveel mense per sekonde kan volgens die model deur die netwerk beweeg voordat
        'n korridor se kapasiteit (Rand.kapasiteit) die beperkende faktor
        word?" Dit vereis kapasiteit per rand eerder as net reistyd.

        'n Kunsmatige put word met 'n voldoende groot, eindige kapasiteit
        aan elke toegelate uitgang gekoppel. Sonder gemete databasiswaardes
        gebruik elke rand VERSTEK_KAPASITEIT; dit is slegs 'n demonstrasie,
        nie 'n voorspelling van werklike skarebeweging nie.

        Brandveiligheidsreël: soos in naaste_veilige_uitgang(), word
        hysbakrande (rand_tipe='HUISBAK') uitgesluit.

        Gee (maks_vloei, bottelnek_kante) terug, waar bottelnek_kante die
        min-snit-rande is wat die deurvloei beperk (elk 'n (van_node,
        na_node, kapasiteit) tuple). Gee None terug as die bronpunt self
        ontoeganklik is of geen positiewe vloei moontlik is nie. 'n Bron
        wat reeds 'n toegelate uitgang is, lewer (0.0, []).
        """
        if bron not in self.nodes:
            raise ValueError(f"Bronpunt '{bron}' nie gevind in grafiek nie.")

        toegelaat = self.toegelate_groepe(gebruiker_tipe)
        geblokkeer = geblokkeerde_nodes or set()

        if not self._is_bruikbaar(bron, toegelaat, geblokkeer):
            return None

        # Geen netwerkvloei is nodig as die persoon reeds by 'n uitgang is.
        # Dit voorkom oneindige vloei en 'n ongeldige JSON-antwoord.
        if self.nodes[bron]["is_nooduitgang"]:
            return 0.0, []
        SUPERPUT = object()  # Kan nooit met 'n databasis-node-ID bots nie.

        # Pas die hospitaalreëls HIER toe: slegs rande tussen bruikbare nodusse,
        # en nooit 'n hysbak (brandveiligheidsreël). Edmonds-Karp self ken geen
        # hospitaalreëls nie en sien net hierdie (van, na, kapasiteit)-lys.
        kante = [
            (van_node, rand.na_node, rand.kapasiteit)
            for van_node, rande in self.adjacency.items()
            if self._is_bruikbaar(van_node, toegelaat, geblokkeer)
            for rand in rande
            if rand.rand_tipe != "HUISBAK"
            and self._is_bruikbaar(rand.na_node, toegelaat, geblokkeer)
        ]

        # 'n Eindige boonste grens voorkom berekeninge met oneindigheid.
        maksimum_kapasiteit = sum(kap for _, _, kap in kante)
        uitgange = [
            node_id for node_id, data in self.nodes.items()
            if data["is_nooduitgang"] and self._is_bruikbaar(node_id, toegelaat, geblokkeer)
        ]
        if not uitgange:
            return None  # Geen nooduitgang beskikbaar of almal geblokkeer.

        # Koppel elke toegelate nooduitgang aan die kunsmatige put. Hierdie
        # rande se kapasiteit is groter as enige vloei, dus beperk hulle nooit
        # die uitkoms nie en kom nie in die min-snit voor nie.
        kante += [(uitgang, SUPERPUT, maksimum_kapasiteit) for uitgang in uitgange]

        maks_vloei, bottelnek_kante = edmonds_karp(kante, bron, SUPERPUT)
        if maks_vloei == 0:
            return None

        # sorted() gee die bottelnekke 'n vaste volgorde, ongeag die randvolgorde.
        return float(maks_vloei), sorted(bottelnek_kante)

    @staticmethod
    def _reconstruct(kom_van: dict[str, str], huidig: str) -> list[str]:
        """
        Herstel die roete deur kom_van-wysers van die doelpunt terug te volg.

        Gee 'n lys node-ID's terug van beginpunt tot doelpunt.
        (Die lys word opgebou van agter na voor en dan omgekeer.)
        """
        pad = [huidig]
        while huidig in kom_van:
            huidig = kom_van[huidig]
            pad.append(huidig)
        pad.reverse()
        return pad


# ---------------------------------------------------------------------------
# Ontruimingsdekking-kontrole (parallelle verwerking Fase 4)
# ---------------------------------------------------------------------------
# Modulevlak-funksies kan deur aparte werkprosesse gebruik word. Elke proses
# laai sy eie grafiek eenmalig; die hooftoepassing stuur slegs nodus-ID's,
# gebruikerstipe en die huidige stel geblokkeerde nodusse saam.

def kontroleer_nodus_dekking(
    graf: HospitaalGrafiek,
    node_id: str,
    gebruiker_tipe: str,
    geblokkeerde_nodes: set[str],
) -> dict:
    """
    Kontroleer of 'n veilige ontruimingsroete van 'n gegewe nodus af steeds
    bestaan, gegewe die huidige stel geblokkeerde nodusse (bv. weens 'n
    aktiewe insident).

    Gee altyd 'n woordeboek terug met minstens 'node_id' en 'bereikbaar'.
    By sukses word uitgangsinligting bygevoeg; by mislukking 'n 'rede'-veld
    sodat die admin-koppelvlak kan onderskei TUSSEN "hierdie nodus is self
    geblokkeer" en "hierdie nodus is afgesny van alle uitgange" — dis nie
    dieselfde probleem vir 'n admin om te evalueer nie.
    """
    # Geval 1: die nodus self is geblokkeer. 'n Ander situasie as "geen
    # uitgang gevind nie" — ons kan nie eers 'n roete hiervandaan begin
    # bereken nie, dus moet ons dit vroeg en eksplisiet uitsonder.
    if node_id in geblokkeerde_nodes:
        return {
            "node_id": node_id,
            "bereikbaar": False,
            "rede": "nodus_geblokkeer",
        }

    resultaat = graf.naaste_veilige_uitgang(
        node_id,
        gebruiker_tipe=gebruiker_tipe,
        geblokkeerde_nodes=geblokkeerde_nodes,
    )

    # Geval 2: geen bereikbare nooduitgang nie — bv. die nodus is deur die
    # geblokkeerde nodusse van alle uitgange afgesny, of elke uitgang is
    # self geblokkeer.
    if resultaat is None:
        return {
            "node_id": node_id,
            "bereikbaar": False,
            "rede": "geen_bereikbare_uitgang",
        }

    # Geval 3: 'n veilige roete is gevind — pak die relevante velde uit.
    pad, tyd_sekondes, afstand_m = resultaat
    return {
        "node_id": node_id,
        "bereikbaar": True,
        "uitgang_node": pad[-1],  # Laaste nodus in die pad is die bereikte uitgang.
        "tyd_sekondes": round(tyd_sekondes, 1),
        "afstand_m": round(afstand_m, 1),
        "node_telling": len(pad),
    }


def kontroleer_alle_nodusse_dekking(
    graf: HospitaalGrafiek,
    gebruiker_tipe: str,
    geblokkeerde_nodes: set[str],
) -> list[dict]:
    """
    Sekwensiële basislyn: loop deur ELKE nodus in die grafiek en kontroleer
    of 'n veilige ontruimingsroete daarvandaan steeds bestaan.

    Loop doelbewus sekwensieel (geen veelprosesverwerking hier nie) — dit is die
    korrektheids- EN spoedbasislyn waarteen die parallelle weergawe hier
    onder vergelyk word.
    """
    return [
        kontroleer_nodus_dekking(graf, node_id, gebruiker_tipe, geblokkeerde_nodes)
        for node_id in graf.nodes
    ]


# Proses-plaaslike veranderlike: bestaan net binne-in 'n werkproses se eie
# geheue, word NOOIT gedeel met die hoofproses of ander werkprosesse nie.
# Bly doelbewus 'n modulevlak-privaat naam (voorloop-onderstreep) — dit
# word nooit buite hierdie lêer ingevoer of direk gebruik nie.
_WERKER_GRAF: Optional[HospitaalGrafiek] = None


def init_werker(db_pad: str) -> None:
    """
    Werkproses-inisialiseerder: word EEN KEER per werkproses aangeroep
    wanneer die ProcessPoolExecutor-poel geskep word (sien kry_dekking_pool()
    in main.py), NIE een keer per taak nie. Laai die grafiek in 'n
    proses-plaaslike globale veranderlike sodat elke daaropvolgende taak
    in dieselfde proses dit sonder herlaai kan hergebruik.

    Word oor die prosesgrens heen aan die poel deurgegee as die
    'initializer'-argument — moet dus 'n gewone, module-vlak funksie wees
    (piekelbaar), nie 'n lambda of geneste funksie nie.
    """
    global _WERKER_GRAF
    _WERKER_GRAF = HospitaalGrafiek(db_pad)


def _kontroleer_nodus_dekking_taak(
    node_id: str,
    gebruiker_tipe: str,
    geblokkeerde_nodes: set[str],
) -> dict:
    """
    Dun omhulsel wat DEUR ELKE WERKTAAK aangeroep word. Neem doelbewus net
    klein, maklik-processeerbare argumente — nooit die grafiek self nie — en
    gebruik eerder die reeds-gelaaide _WERKER_GRAF vanaf init_werker().
    """
    if _WERKER_GRAF is None:
        raise RuntimeError(
            "_WERKER_GRAF is nie geïnitialiseer nie — is init_werker() as "
            "die poel se initializer ingestel?"
        )
    return kontroleer_nodus_dekking(
        _WERKER_GRAF, node_id, gebruiker_tipe, geblokkeerde_nodes
    )


def kontroleer_alle_nodusse_dekking_parallel(
    node_ids: list[str],
    gebruiker_tipe: str,
    geblokkeerde_nodes: set[str],
    uitvoerder: ProcessPoolExecutor,
) -> list[dict]:
    """
    Parallelle weergawe van kontroleer_alle_nodusse_dekking(): dien EEN
    taak per nodus in by 'n reeds-bestaande ProcessPoolExecutor-poel en
    wag vir almal se resultate.

    Die uitvoerder word deur die toepassing besit en hergebruik. Só word
    werkprosesse nie vir elke versoek opnuut begin nie. Resultate behou
    die invoervolgorde, ongeag die volgorde waarin take voltooi word.
    """
    take = [
        uitvoerder.submit(
            _kontroleer_nodus_dekking_taak, node_id, gebruiker_tipe, geblokkeerde_nodes
        )
        for node_id in node_ids
    ]
    return [taak.result() for taak in take]


def bou_demo_db(db_pad: str, skema_pad: str, seed_pad: str):
    """
    Herskep die SQLite-databasis uit die skema- en voorbeelddata-lêers.

    Word gebruik:
      • Tydens ontwikkeling by elke opstart (AUTO_HERBOU_DB=true in main.py).
      • In eenheidstoetse om 'n skoon databasis te verseker.
      • Wanneer 'n nuwe omgewing vir die eerste keer ingestel word.
    """
    if os.path.exists(db_pad):
        os.remove(db_pad)
    with closing(sqlite3.connect(db_pad)) as conn:
        with open(skema_pad, encoding="utf-8") as f:
            conn.executescript(f.read())
        with open(seed_pad, encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()


# ---------------------------------------------------------------------------
# Handmatige demonstrasie (voer uit as: python HospitaalGrafiek.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    bou_demo_db("hospitaal.db", "Skema.sql", "SeedData.sql")
    g = HospitaalGrafiek("hospitaal.db")

    print("=== PUBLIEK: Hoof Ingang → Radiologie ===")
    resultaat = g.astar("MAIN-G-ENT", "SYGEBOU-1-RAD", gebruiker_tipe="PUBLIEK")
    if resultaat:
        pad, koste, afstand = resultaat
        print(f"Pad ({koste:.0f}s, {afstand:.0f}m): " + " → ".join(pad))
    else:
        print("Geen roete gevind nie.")

    print("\n=== PUBLIEK probeer ICU bereik (moet geblokkeer word) ===")
    resultaat = g.astar("MAIN-G-ENT", "MAIN-2-ICU", gebruiker_tipe="PUBLIEK")
    print("Geblokkeer soos verwag." if resultaat is None else f"Onverwagte roete: {resultaat}")

    print("\n=== PERSONEEL: Hoof Ingang → ICU ===")
    resultaat = g.astar("MAIN-G-ENT", "MAIN-2-ICU", gebruiker_tipe="PERSONEEL")
    if resultaat:
        pad, koste, afstand = resultaat
        print(f"Pad ({koste:.0f}s, {afstand:.0f}m): " + " → ".join(pad))

    print("\n=== Minimum Spanboom (hele grafiek) ===")
    mst_kante, mst_gewig = g.bereken_min_spanboom()
    print(f"{len(mst_kante)} kante, totale gewig {mst_gewig:.0f}s")

    print("\n=== Maksimum vloei: Nooddienste → alle nooduitgange ===")
    resultaat = g.maks_vloei_na_uitgange("MAIN-G-ER", gebruiker_tipe="PUBLIEK")
    if resultaat:
        maks, bottelnekke = resultaat
        print(f"Maksimum vloei: {maks:.1f} persone/s")
        print(f"Bottelnekrande: {bottelnekke}")
