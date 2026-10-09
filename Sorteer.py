"""============================================================================
Sorteer.py
==========
Handgeskrewe sorteeralgoritmes vir die Hospitaal Navigasiestelsel.

Hierdie module bevat TWEE sorteeralgoritmes.
Geen ingeboude sorteerfunksie word gebruik nie.

    1. insertion_sort() - vir klein lyste.
    2. merge_sort()     - vir groter lyste.

Waarom twee algoritmes en nie net een nie?
-------------------------------------------
Die twee algoritmes is goed vir verskillende situasies, en die keuse hang af
van hoe die lys groei, nie van hoe groot dit vandag toevallig is nie:

  * Invoegsortering doen in die beste geval net n-1 vergelykings (wanneer die
    lys al gesorteer is) en benodig geen rekursie nie. Hierdie weergawe
    maak wel sleutelpare en 'n afsonderlike uitvoerlys.
    Dit is 'n geskikte keuse vir lyste wat volgens hulle aard klein
    bly - die hospitaal het byvoorbeeld net 2 geboue en 5 vloere.

  * Saamsmeltsortering se O(n log n) is die regte keuse vir lyste wat saam
    met die hospitaal groei. Die demo-databasis het net 26 nodusse, maar 'n
    werklike hospitaal het maklik 'n paar duisend.

Albei algoritmes is stabiel
---------------------------
'n Stabiele sorteerder hou twee items met dieselfde sleutel in hulle
oorspronklike onderlinge volgorde. Dit maak saak wanneer ons op een veld
sorteer en die vorige volgorde binne gelyke groepe wil behou.

Hoe die sleutel werk
---------------------
Elke funksie neem 'n opsionele 'sleutel'-parameter wat bepaal WAAROP
gesorteer word. Dit kan vier vorme aanneem:

    sleutel=None                            - sorteer op die item self (bv. 'n lys teks)
    sleutel="naam"                          - sorteer op item["naam"]
    sleutel=("gebou_id", "level_nommer")    - sorteer op twee velde, die eerste eerste
    sleutel=lambda r: r["etiket"]           - sorteer op enigiets wat jy self bereken

"""
# Die drumpel waar saamsmeltsortering na invoegsortering oorskakel.
# Twaalf is 'n instelbare keuse vir hierdie implementasie, nie 'n gemete
# optimum nie. Hierdie algoritme is nie Python se ingeboude Timsort nie.
DREMPEL = 12


# ---------------------------------------------------------------------------
# Hulpfunksies: sleutels bereken, en items in (sleutel, waarde)-pare verpak
# ---------------------------------------------------------------------------

def _sleutelwaarde(item, sleutel):
    """
    Bereken die sorteersleutel van een item.
    Word een keer per item aangeroep, nie een keer per vergelyking nie.
    Sleutelberekening binne die vergelykingslus sou tot O(n²) aanroepe
    kon verg, teenoor die O(n) aanroepe hier.
    """
    if sleutel is None:
        # Geen sleutel gegee nie: die item is sy eie sleutel.
        return item

    if callable(sleutel):
        # 'n Funksie of lambda is gegee: laat dit die sleutel bereken.
        return sleutel(item)

    if isinstance(sleutel, (tuple, list)):
        # Meer as een veld: gee 'n tuple terug. Python vergelyk 'n tuple van
        # links na regs, net soos 'ORDER BY a, b' eers op a en dan op b
        # sorteer. Die tuple word hier opgebou, nooit vergelyk teen die item
        # self nie.
        return tuple(item[veld] for veld in sleutel)


    return item[sleutel]


def _maak_pare(items, sleutel):
    """
    Verpak elke item saam met sy sleutel as 'n (sleutel, waarde)-paar.

    Redes vir pare:

      1. Die sleutel word net een keer per item bereken.
      2. Die algoritmes vergelyk NET paar[0], nooit die paar self nie. Dit is
         noodsaaklik, want die waardes is dikwels woordeboeke of sqlite3.Row-
         objekte, en Python kan nie twee woordeboeke met < of > vergelyk nie.
         Sou ons die pare self vergelyk, sou Python by 'n gelykop-sleutel na
         die tweede element van die tuple kyk en 'n TypeError gooi.
    """
    return [(_sleutelwaarde(item, sleutel), item) for item in items]


def _pak_uit(pare):
    """Gooi die sleutels weg en gee net die gesorteerde items terug."""
    return [paar[1] for paar in pare]


# ---------------------------------------------------------------------------
# ALGORITME 1: Invoegsortering (insertion sort)
# ---------------------------------------------------------------------------

def insertion_sort(items, sleutel=None):
    """
    Sorteer 'n lys met invoegsortering. Gee 'n NUWE lys terug; die lys wat
    ingegee is bly onveranderd.
    Gebruik dit vir lyste wat volgens hulle aard klein bly, soos die
    hospitaal se geboue, vloere en noodkodes.
    """
    pare = _maak_pare(items, sleutel)
    return _pak_uit(_insertion_sorteer_pare(pare))


def _insertion_sorteer_pare(pare):
    """
    Die werklike invoegsortering, op 'n lys (sleutel, waarde)-pare.
    """
    lys = list(pare)   # Kopie, sodat die oorspronklike lys onaangeraak bly.

    # Die item op indeks 0 is alleen, en 'n lys van een item is per definisie
    # al gesorteer. Daarom begin ons by indeks 1.
    for i in range(1, len(lys)):

        huidige = lys[i]        # Die paar wat ons nou op sy plek gaan invoeg.
        j = i - 1               # Ons kyk van hier af terug na links.

        # Skuif elke paar wat groter is as 'huidige' een plek na regs, en
        # skep so 'n oop gaping waar 'huidige' moet inpas.
        while j >= 0 and lys[j][0] > huidige[0]:
            lys[j + 1] = lys[j]   # Skuif een plek na regs.
            j -= 1                # En kyk verder na links.

        # Die while-lus het gestop, dus lys[j] is klein genoeg (of ons is by
        # die begin van die lys). Die gaping is by j + 1.
        lys[j + 1] = huidige

    return lys


# ---------------------------------------------------------------------------
# ALGORITME 2: Saamsmeltsortering (merge sort)
# ---------------------------------------------------------------------------

def merge_sort(items, sleutel=None, drempel=DREMPEL):
    """
    Sorteer 'n lys met saamsmeltsortering. Gee 'n NUWE lys terug; die lys wat
    ingegee is bly onveranderd.

    Die drumpel
    ---------------------------------
    Rekursie kos iets: elke aanroep bou 'n nuwe raam op die stapel en sny
    nuwe lysies af. Vir 'n klein lysie is daardie oorhoofse koste meer as wat
    die beter groeitempo spaar. Daarom skakel hierdie implementasie oor na
    invoegsortering sodra 'n stukkie kleiner as 'drempel' word. Dit verander
    nie die uitkoms nie. Vir 'n vaste drumpel bly die slegste tydskompleksiteit
    O(n log n); 'n drumpel groter as die hele invoer gebruik egter net
    invoegsortering en kan O(n²) kos. 'n Spoedwins hang van die invoer af.
    """
    pare = _maak_pare(items, sleutel)
    return _pak_uit(_merge_sorteer_pare(pare, drempel))


def _merge_sorteer_pare(pare, drempel):

    # Stopvoorwaarde 1: 'n lys van 0 of 1 item is al gesorteer. Sonder die
    # sou die rekursie nooit ophou nie.
    """Saamsmeltsortering op (sleutel, waarde)-pare; klein stukke gaan na invoegsortering (sien drempel)."""
    if len(pare) <= 1:
        return pare

    # Stopvoorwaarde 2: klein stukkies word met
    # invoegsortering afgehandel.
    if len(pare) <= drempel:
        return _insertion_sorteer_pare(pare)

    # VERDEEL: sny in die middel.
    middel = len(pare) // 2

    # HEERS: sorteer elke helfte deur hierdie funksie weer op homself aan te
    # roep. Elke aanroep werk op 'n korter lys, dus bereik ons uiteindelik
    # altyd een van die twee stopvoorwaardes.
    links = _merge_sorteer_pare(pare[:middel], drempel)
    regs  = _merge_sorteer_pare(pare[middel:], drempel)

    # KOMBINEER: smelt die twee gesorteerde helftes saam.
    return _smelt_saam(links, regs)


def _smelt_saam(links, regs):
    """
    Smelt die twee gesorteerde lyste saam tot een gesorteerde lys.
    """
    saam = []
    i = 0   # Vinger in die linkerlys.
    j = 0   # Vinger in die regterlys.

    # Solank albei lyste nog items oor het, vergelyk die twee voorste items.
    while i < len(links) and j < len(regs):

        # Let op die <= en nie < nie. By 'n gelyke sleutel word die item uit
        # die linkerlys eerste geneem, en die linkerlys was die vroeer helfte
        # van die oorspronklike lys. Gelyke items behou dus hulle
        # oorspronklike volgorde - dit is wat die algoritme stabiel maak.
        if links[i][0] <= regs[j][0]:
            saam.append(links[i])
            i += 1
        else:
            saam.append(regs[j])
            j += 1

    # Een van die twee lyste is nou leeg. Die ander een se oorblywende items
    # is al gesorteer en al groter as alles wat ons klaar geneem het, dus kan
    # hulle net soos hulle is agteraan geheg word.
    while i < len(links):
        saam.append(links[i])
        i += 1

    while j < len(regs):
        saam.append(regs[j])
        j += 1

    return saam


# ---------------------------------------------------------------------------
# Handmatige demonstrasie
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    print("=== 1. Gewone lys teks, geen sleutel ===")
    node_ids = ["MAIN-2-ICU", "MAIN-G-ENT", "SYGEBOU-1-RAD", "MAIN-1-WARDA"]
    print("  voor :", node_ids)
    print("  na   :", insertion_sort(node_ids))
    print("  (die oorspronklike lys is steeds onveranderd:", node_ids, ")")

    print("\n=== 2. Lys woordeboeke, sorteer op een veld ===")
    geboue = [
        {"gebou_id": "SYGEBOU", "naam": "Sygebou"},
        {"gebou_id": "MAIN",    "naam": "Main Hospitaal Gebou"},
    ]
    for g in insertion_sort(geboue, sleutel="naam"):
        print("  ", g["naam"])

    print("\n=== 3. Sorteer op TWEE velde (vervang 'ORDER BY gebou_id, level_nommer') ===")
    vloere = [
        {"vloer_id": "MAIN-2",    "gebou_id": "MAIN",    "level_nommer": 2},
        {"vloer_id": "SYGEBOU-G", "gebou_id": "SYGEBOU", "level_nommer": 0},
        {"vloer_id": "MAIN-G",    "gebou_id": "MAIN",    "level_nommer": 0},
        {"vloer_id": "SYGEBOU-1", "gebou_id": "SYGEBOU", "level_nommer": 1},
        {"vloer_id": "MAIN-1",    "gebou_id": "MAIN",    "level_nommer": 1},
    ]
    for v in insertion_sort(vloere, sleutel=("gebou_id", "level_nommer")):
        print(f"   {v['gebou_id']:<8} vlak {v['level_nommer']}  ({v['vloer_id']})")

    print("\n=== 4. Saamsmeltsortering op 'n groter lys ===")
    import random
    groot = [random.randint(1, 999) for _ in range(20)]
    print("  voor :", groot)
    print("  na   :", merge_sort(groot))

    print("\n=== 5. Albei algoritmes gee altyd dieselfde antwoord ===")
    for toets in ([], [7], [3, 1, 2], [5, 5, 5], list(range(30)), list(range(30, 0, -1))):
        if insertion_sort(toets) != merge_sort(toets):
            print("  FOUT by", toets)
            break
    else:
        print("  Ja - op al die toetsgevalle stem hulle presies ooreen.")

    print("\n=== 6. Stabiliteit: gelyke sleutels behou hulle volgorde ===")
    pasiente = [
        {"naam": "Anje",   "vloer": 1},
        {"naam": "Ruwan",  "vloer": 1},
        {"naam": "Wessel", "vloer": 0},
        {"naam": "Ronel",  "vloer": 1},
    ]
    # Almal op vloer 1 moet in hulle oorspronklike orde bly.
    for p in merge_sort(pasiente, sleutel="vloer"):
        print(f"   vloer {p['vloer']}  {p['naam']}")
