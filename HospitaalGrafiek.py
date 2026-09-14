"""============================================================================
HospitaalGrafiek.py
====================
Grafiek-laaier en roete-algoritmes vir die Hospitaal Navigasiestelsel.

Hierdie module laai die topologiese grafiek (nodusse en rande) uit die
SQLite-databasis en bied twee roete-algoritmes aan:

  1. astar()              — A* vir normale navigasie tussen twee nodusse.
  2. naaste_veilige_uitgang() — Multi-bron Dijkstra vir ontruimingsmodus.

Waarom A* vir normale navigasie?
---------------------------------
A* is 'n ingeligte soekalgoritme wat 'n heuristiek gebruik om die soekruimte
te sny. Die heuristiek (reguitlynafstand + vloerveranderingstraf) is toelaatbaar
(dit oorskat nooit die werklike koste nie), sodat A* gewaarborg is om die
optimale pad te vind. In 'n klein hospitaalgrafiek (<100 nodusse) is A* meer
as voldoende en bied dit ook 'n verstaanbare uitbreipunt vir toekomstige
uitbreidings soos dinamiese verkeerslading.

Waarom Multi-bron Dijkstra vir ontruimingsmodus?
-------------------------------------------------
Tydens 'n noodsituasie is ons doel NIE om na 'n spesifieke bestemming te
navigeer nie — ons wil die NAASTE veilige nooduitgang vind uit ENIGE van die
moontlike uitgange. Hierdie probleem het "single-source, multiple-target
shortest path" en word doeltreffend opgelos deur omgekeerde multi-bron
Dijkstra:

  • Alle nooduitgange word gelyktydig as beginpunte in die hoop gelaai
    (elk met koste 0).
  • Dijkstra brei omgekeerd uit (deur die omgekeerde aangrensingsstruktuur)
    totdat dit die gebruiker se beginpunt bereik.
  • Die eerste keer dat die beginpunt bereik word, is dit gewaarborg die
    goedkoopste (tyd-optimale) pad na die naaste uitgang.

Dit is wiskundig ekwivalent aan n enkele voorwaartse soektog na 'n
versameling teikens, maar is dikwels vinniger omdat die soektog stop sodra
een uitgang gevind word. 'n Heuristiek soos in A* sou hier ook kon werk,
maar sou 'n skenking verg na ELKE moontlike uitgang — Dijkstra sonder
heuristiek is hier eenvoudiger en onfeilbaar korrek.

Brandveiligheidsreël: Hysbakrande word outomaties uitgelaat tydens
ontruiming — slegs trappe, lugbrûe en tonnels word toegelaat.
"""

import sqlite3
import math
import heapq
from dataclasses import dataclass, field
from typing import Optional
from Boom24 import Boom24

# Straftyd (sekondes) wat bygevoeg word vir elke vloerverandering in die
# A*-heuristiek. Hierdie waarde verseker dat die heuristiek toelaatbaar bly
# terwyl dit die algoritme aanmoedig om onnodige vloerwisselings te vermy.
VLOER_VERANDER_PENALTY_S = 20.0


@dataclass
class Rand:
    """Verteenwoordig 'n geweegde verbinding tussen twee nodusse in die grafiek."""
    na_node: str
    gewig_s: float      # Totale reistyd (basisgewig + wagtyd) in sekondes.
    rand_tipe: str      # Byvoorbeeld 'GANG', 'HUISBAK', 'TRAPPE', 'LUGBRUG', 'TONNEL'.
    vloer_verander: int # Aantal vloere wat hierdie rand oorsteek (0 vir horisontale rande).
    afstand_m: float    # Fisiese loopafstand in meter; 0 vir hysbakbewegings.


class HospitaalGrafiek:
    """
    Laai die hospitaalgrafiek uit SQLite en bied roete-algoritmes aan.

    Die grafiek word eenmalig by toepassingsopstart in geheue gelaai
    (via FastAPI se lifespan-hanteerder in main.py) en word dan vir alle
    versoeke hergebruik — geen herhaalde databasistoegange tydens roetebepaling.
    """

    def __init__(self, db_pad: str):
        self.db_pad = db_pad
        # Elke node-ID word gekoppel aan sy metadata (vloer, posisie, toegangsbeperking).
        self.nodes: dict[str, dict] = {}
        # Aangrensingsstruktuur: elke node-ID word gekoppel aan sy lys uitgaande rande.
        self.adjacency: dict[str, list[Rand]] = {}
        self._load()

    def _load(self):
        """Laai alle nodusse en rande uit die SQLite-databasis in geheue."""
        conn = sqlite3.connect(self.db_pad)
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

        # Laai alle rande en voeg ook omgekeerde rande by vir bidirectionele verbindings.
        cur.execute("""
            SELECT van_node, na_node, rand_tipe, afstand_m,
                   basis_gewig_s, wag_penalty_s, vloer_verander, bidirectional
            FROM rande
        """)
        for row in cur.fetchall():
            gewig = row["basis_gewig_s"] + row["wag_penalty_s"]
            e = Rand(row["na_node"], gewig, row["rand_tipe"], row["vloer_verander"], row["afstand_m"])
            self.adjacency[row["van_node"]].append(e)
            if row["bidirectional"]:
                e_rev = Rand(row["van_node"], gewig, row["rand_tipe"], row["vloer_verander"], row["afstand_m"])
                self.adjacency[row["na_node"]].append(e_rev)

        conn.close()

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

    def toegelate_groepe(self, gebruiker_tipe: str) -> set[str]:
        """
        Gee die stel beperkte groepe terug wat hierdie gebruikerstipe mag betree.

        Byvoorbeeld: 'PERSONEEL' kry {'SLEGS_PERSONEEL', 'SLEGS_ICU'}, terwyl
        'PUBLIEK' 'n leë stel kry (mag geen beperkte areas betree nie).
        Gooi ValueError as die gebruikerstipe nie in die databasis bestaan nie.
        """
        conn = sqlite3.connect(self.db_pad)
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM gebruiker_tipes WHERE gebruiker_tipe = ?",
            (gebruiker_tipe,),
        )
        if cur.fetchone() is None:
            conn.close()
            raise ValueError(f"Ongeldige gebruikerstipe: {gebruiker_tipe}")

        cur.execute(
            "SELECT beperkte_groep FROM toegang_toestemmings WHERE gebruiker_tipe = ?",
            (gebruiker_tipe,),
        )
        groepe = {r[0] for r in cur.fetchall()}
        conn.close()
        return groepe

    def soek_bestemmings(self, soekterm: str = "", limiet: int = 20) -> list[dict]:
        """
        Soek naam, node-ID, tipe, gebou en vloer in die 2-4-boom se metadata.

        Gebruik deur die /destinations eindpunt in main.py sodat die webkoppelvlak
        mensleesbare etikette (met gebou- en vloerinligting) kan vertoon sonder
        dat die gebruiker raw node-ID's hoef te ken.
        """
        # Kopieë beskerm die indeks se metadata teen verandering deur 'n leser.
        return [dict(item) for item in
                self.bestemmingsindeks.soek_metadata(soekterm, limiet)]

    def _heuristic(self, a: str, b: str) -> float:
        """
        Skat die oorblywende tydkoste tussen twee nodusse vir A*.

        Gebruik Euklidiese afstand in die vloerplan-koördinatestelsel plus 'n
        vaste straf vir elke vloerverskil. Die heuristiek is toelaatbaar
        (onderskat nooit die werklike koste nie) omdat die Euklidiese afstand
        altyd 'n ondergrens is vir die werklike padlengte en die vloerstraf
        ooreenstem met die minimum moontlike vloerveranderingskoste.
        """
        ax, ay = self.nodes[a]["pos"]
        bx, by = self.nodes[b]["pos"]
        planar = math.hypot(ax - bx, ay - by)
        vloer_delta = abs(self.nodes[a]["level"] - self.nodes[b]["level"])
        return planar + vloer_delta * VLOER_VERANDER_PENALTY_S

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
            raise ValueError("begin/doel node nie gevind in grafiek nie.")

        toegelaat = self.toegelate_groepe(gebruiker_tipe)
        geblokkeer = geblokkeerde_nodes or set()

        def is_bruikbaar(node_id: str) -> bool:
            """Keur 'n nodus goed as dit nie geblokkeer of beperk is nie."""
            if node_id in geblokkeer:
                return False
            groep = self.nodes[node_id]["beperkte_groep"]
            return groep is None or groep in toegelaat

        # Kyk vroeg of begin of doel self ontoeganklik is.
        if not is_bruikbaar(begin) or not is_bruikbaar(doel):
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
                if not is_bruikbaar(rand.na_node):
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

        Die omgekeerde aangrensingsstruktuur verseker dat die herstel-stap
        ('_reconstruct') 'n pad van 'begin' → uitgang produseer.

        Brandveiligheidsreël
        ---------------------
        Hysbakrande (rand_tipe='HUISBAK') word uitgelaat — slegs trappe,
        lugbrûe en tonnels is tydens ontruiming toegelaat. Dit weerspieël
        standaard brandveiligheidsprotokol (SANS 10400-T).

        Gee None terug as geen bereikbare nooduitgang bestaan nie.
        """
        if begin not in self.nodes:
            raise ValueError(f"Beginpunt '{begin}' nie gevind in grafiek nie.")

        toegelaat = self.toegelate_groepe(gebruiker_tipe)
        geblokkeer = geblokkeerde_nodes or set()

        def is_bruikbaar(node_id: str) -> bool:
            if node_id in geblokkeer:
                return False
            groep = self.nodes[node_id]["beperkte_groep"]
            return groep is None or groep in toegelaat

        if not is_bruikbaar(begin):
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
                # Bidirectionele rande: voeg ook die direkte rigting by as omgekeerde kant.
                omgekeerde[van_node].append(
                    Rand(rand.na_node, rand.gewig_s, rand.rand_tipe, rand.vloer_verander, rand.afstand_m)
                )

        # Verwyder duplikate wat ontstaan het deurdat tweerigting rande twee keer verwerk is.
        for nid in omgekeerde:
            gesien: set[tuple] = set()
            uniek: list[Rand] = []
            for rand in omgekeerde[nid]:
                sleutel = (rand.na_node, rand.rand_tipe)
                if sleutel not in gesien:
                    gesien.add(sleutel)
                    uniek.append(rand)
            omgekeerde[nid] = uniek

        # --- Multibron Dijkstra ---
        # Laai alle bereikbare nooduitgange as beginpunte met koste 0.
        g_score: dict[str, float] = {}
        afstand_score: dict[str, float] = {}
        kom_van: dict[str, str] = {}
        hoop: list[tuple[float, str]] = []  # (koste, node_id)

        for nid, data in self.nodes.items():
            if data["is_nooduitgang"] and is_bruikbaar(nid):
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
                if not is_bruikbaar(bure):
                    continue
                tentatiewe_g = koste_so_ver + rand.gewig_s
                if tentatiewe_g < g_score.get(bure, math.inf):
                    g_score[bure] = tentatiewe_g
                    afstand_score[bure] = afstand_score[huidig] + rand.afstand_m
                    kom_van[bure] = huidig
                    heapq.heappush(hoop, (tentatiewe_g, bure))

        return None  # Geen bereikbare nooduitgang gevind nie.

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


def bou_demo_db(db_pad: str, skema_pad: str, seed_pad: str):
    """
    Herskep die SQLite-databasis uit die skema- en voorbeelddata-lêers.

    Word gebruik:
      • Tydens ontwikkeling by elke opstart (AUTO_HERBOU_DB=true in main.py).
      • In eenheidstoetse om 'n skoon databasis te verseker.
      • Wanneer 'n nuwe omgewing vir die eerste keer ingestel word.
    """
    import os
    if os.path.exists(db_pad):
        os.remove(db_pad)
    conn = sqlite3.connect(db_pad)
    with open(skema_pad) as f:
        conn.executescript(f.read())
    with open(seed_pad) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


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
