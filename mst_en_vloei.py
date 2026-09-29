"""
Nuwe algoritmes om by HospitaalGrafiek.py te voeg:
1. Minimum Spanboom (Kruskal) - vind goedkoopste verbindingsnetwerk
2. Maksimum Vloei (Edmonds-Karp) - vind bottelnekke na noodurgange

Pas hierdie metodes by die HospitaalGrafiek-klas in, of voeg hulle
by as los funksies wat julle bestaande graaf-datastruktuur aanvaar.

AANNAME oor datastruktuur (pas gerus aan by julle werklike struktuur -
deel HospitaalGrafiek.py met my as die vorm anders is):
- nodusse: 'n stel/lys van nodus-ID's
- kante (vir MST):    lys van (nodus_a, nodus_b, gewig) tuples
- kante (vir vloei):  lys van (nodus_a, nodus_b, kapasiteit) tuples
"""

from collections import defaultdict, deque


# ============================================================
# 1. MINIMUM SPANBOOM - Kruskal se algoritme
# ============================================================

class UnionFind:
    """Help-klas vir Kruskal: hou by watter nodusse reeds verbind is."""

    def __init__(self, nodusse):
        self.ouer = {n: n for n in nodusse}
        self.rang = {n: 0 for n in nodusse}

    def vind(self, x):
        if self.ouer[x] != x:
            self.ouer[x] = self.vind(self.ouer[x])  # pad-kompressie
        return self.ouer[x]

    def unie(self, x, y):
        wortel_x, wortel_y = self.vind(x), self.vind(y)
        if wortel_x == wortel_y:
            return False  # sou 'n siklus vorm - moet nie by MST kom nie
        if self.rang[wortel_x] < self.rang[wortel_y]:
            wortel_x, wortel_y = wortel_y, wortel_x
        self.ouer[wortel_y] = wortel_x
        if self.rang[wortel_x] == self.rang[wortel_y]:
            self.rang[wortel_x] += 1
        return True


def bereken_min_spanboom(nodusse, kante):
    """
    nodusse: iterable van nodus-ID's
    kante:   lys van (nodus_a, nodus_b, gewig) tuples

    Gee terug: (mst_kante, totale_gewig)
        mst_kante is 'n lys (nodus_a, nodus_b, gewig) wat die MST vorm
    """
    gesorteerde_kante = sorted(kante, key=lambda k: k[2])
    uf = UnionFind(nodusse)
    mst_kante = []
    totale_gewig = 0

    for a, b, gewig in gesorteerde_kante:
        if uf.unie(a, b):
            mst_kante.append((a, b, gewig))
            totale_gewig += gewig

    return mst_kante, totale_gewig


# ============================================================
# 2. MAKSIMUM VLOEI - Edmonds-Karp
# ============================================================

def edmonds_karp(kante, bron, put):
    """
    kante: lys van (nodus_a, nodus_b, kapasiteit) tuples (gerig)
    bron:  begin-nodus
    put:   'n super-put wat al die noodurgange verteenwoordig -
           skep 'n kunsmatige nodus gekoppel aan elke werklike uitgang
           met 'n groot/oneindige kapasiteit

    Gee terug: (maks_vloei_waarde, min_snit_kante)
        min_snit_kante is die bottelneck-kante wat die vloei beperk
    """
    kapasiteit = defaultdict(dict)
    for a, b, kap in kante:
        kapasiteit[a][b] = kapasiteit[a].get(b, 0) + kap
        kapasiteit[b].setdefault(a, 0)  # residuele kant

    def bfs_vind_pad():
        voorganger = {bron: None}
        wagry = deque([bron])
        while wagry:
            huidige = wagry.popleft()
            if huidige == put:
                pad = []
                node = put
                while voorganger[node] is not None:
                    vorige = voorganger[node]
                    pad.append((vorige, node))
                    node = vorige
                return list(reversed(pad))
            for buur, kap in kapasiteit[huidige].items():
                if kap > 0 and buur not in voorganger:
                    voorganger[buur] = huidige
                    wagry.append(buur)
        return None

    maks_vloei = 0
    while True:
        pad = bfs_vind_pad()
        if pad is None:
            break
        vloei_langs_pad = min(kapasiteit[a][b] for a, b in pad)
        for a, b in pad:
            kapasiteit[a][b] -= vloei_langs_pad
            kapasiteit[b][a] += vloei_langs_pad
        maks_vloei += vloei_langs_pad

    # min-snit: nodusse steeds bereikbaar van bron in finale residuele graaf
    bereikbaar = {bron}
    wagry = deque([bron])
    while wagry:
        huidige = wagry.popleft()
        for buur, kap in kapasiteit[huidige].items():
            if kap > 0 and buur not in bereikbaar:
                bereikbaar.add(buur)
                wagry.append(buur)

    min_snit_kante = [
        (a, b, kap) for a, b, kap in kante
        if a in bereikbaar and b not in bereikbaar
    ]

    return maks_vloei, min_snit_kante


# ============================================================
# 3. VOORBEELD-GEBRUIK (verwyder/pas aan sodra ingesluit in HospitaalGrafiek.py)
# ============================================================

if __name__ == "__main__":
    # Klein voorbeeldgraaf om te toets - vervang met julle werklike nodus/kant-data
    nodusse = ["Ingang", "Gang1", "Gang2", "Saal_A", "Uitgang1", "Uitgang2"]
    mst_kante_toets = [
        ("Ingang", "Gang1", 5),
        ("Ingang", "Gang2", 8),
        ("Gang1", "Gang2", 2),
        ("Gang1", "Saal_A", 4),
        ("Gang2", "Uitgang1", 3),
        ("Saal_A", "Uitgang2", 6),
    ]
    mst, gewig = bereken_min_spanboom(nodusse, mst_kante_toets)
    print("MST kante:", mst)
    print("Totale gewig:", gewig)

    vloei_kante_toets = [
        ("Ingang", "Gang1", 10),
        ("Ingang", "Gang2", 5),
        ("Gang1", "Uitgang1", 4),
        ("Gang1", "Saal_A", 6),
        ("Gang2", "Uitgang1", 3),
        ("Saal_A", "Uitgang2", 8),
        ("Uitgang1", "SUPER_PUT", 999),
        ("Uitgang2", "SUPER_PUT", 999),
    ]
    maks, bottelnekke = edmonds_karp(vloei_kante_toets, "Ingang", "SUPER_PUT")
    print("Maksimum vloei na uitgange:", maks)
    print("Bottelneck-kante (min-snit):", bottelnekke)