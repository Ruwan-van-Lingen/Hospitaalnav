"""============================================================================
test_sorteer.py
===============
Geoutomatiseerde toetse vir die sorteeralgoritmes in Sorteer.py.

Voer uit met:
    python -m pytest test_sorteer.py -v

Toetsdekking
-------------
  * Randgevalle: leeg, een item, alles dieselfde      (test_randgevalle_*)
  * Geordend en volledig op baie vorme van invoer     (test_*_sorteer_korrek)
  * Die twee algoritmes stem altyd ooreen             (test_albei_algoritmes_stem_ooreen)
  * Stabiliteit van albei algoritmes                  (test_*_is_stabiel)
  * Al vier vorme van die sleutel-parameter           (test_sleutel_*)
  * Die invoerlys word nooit verander nie             (test_invoerlys_bly_onveranderd)
  * Die hibriede drumpel verander nie die uitkoms nie (test_drempel_*)
  * Werklike hospitaaldata word reg gesorteer         (test_hospitaal_*)
============================================================================
"""

from collections import Counter

import pytest

from Sorteer import insertion_sort, merge_sort


# ---------------------------------------------------------------------------
# Hulpfunksies vir die toetse self
# ---------------------------------------------------------------------------

def is_geordend(lys, sleutel=None):
    """Kyk of die lys in nie-dalende volgorde is, met dieselfde sleutelreëls as Sorteer.py."""
    def waarde(item):
        if sleutel is None:
            return item
        if callable(sleutel):
            return sleutel(item)
        if isinstance(sleutel, (tuple, list)):
            return tuple(item[veld] for veld in sleutel)
        return item[sleutel]

    for i in range(len(lys) - 1):
        if waarde(lys[i]) > waarde(lys[i + 1]):
            return False
    return True


def is_volledig(voor, na):
    """Kyk of albei lyste presies dieselfde items bevat (niks verlore of bygevoeg nie)."""
    return Counter(voor) == Counter(na)


def is_korrek_gesorteer(voor, na):
    """Gesorteer EN volledig."""
    return is_geordend(na) and is_volledig(voor, na)


# 'n Verskeidenheid invoerpatrone wat elke algoritme moet hanteer. Die
# patrone is doelbewus gekies om die bekende probleme te dek: al gesorteer,
# presies agterstevoor, duplikate, en lengtes weerskante van die hibriede
# drumpel van 12.
INVOERPATRONE = [
    pytest.param([],                              id="leeg"),
    pytest.param([42],                            id="een_item"),
    pytest.param([2, 1],                          id="twee_omgeruil"),
    pytest.param([1, 2],                          id="twee_reeds_reg"),
    pytest.param([3, 1, 4, 1, 5, 9, 2, 6],        id="klein_gemeng"),
    pytest.param([5, 5, 5, 5],                    id="alles_dieselfde"),
    pytest.param(list(range(11)),                  id="onder_drempel_gesorteer"),
    pytest.param(list(range(11, 0, -1)),           id="onder_drempel_omgekeer"),
    pytest.param(list(range(40)),                  id="bo_drempel_gesorteer"),
    pytest.param(list(range(40, 0, -1)),           id="bo_drempel_omgekeer"),
    pytest.param([7] * 30,                         id="bo_drempel_duplikate"),
    pytest.param([0, -5, 3, -2, 8, -9, 1],         id="negatiewe_getalle"),
    pytest.param(["saal", "ICU", "radiologie", "Apteek", "or"], id="teks_gemengde_kas"),
]


# ---------------------------------------------------------------------------
# Kerntoetse: is die uitvoer korrek gesorteer?
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("invoer", INVOERPATRONE)
def test_insertion_sort_sorteer_korrek(invoer):
    resultaat = insertion_sort(invoer)
    assert is_korrek_gesorteer(invoer, resultaat)
    assert len(resultaat) == len(invoer)


@pytest.mark.parametrize("invoer", INVOERPATRONE)
def test_merge_sort_sorteer_korrek(invoer):
    resultaat = merge_sort(invoer)
    assert is_korrek_gesorteer(invoer, resultaat)
    assert len(resultaat) == len(invoer)


@pytest.mark.parametrize("invoer", INVOERPATRONE)
def test_albei_algoritmes_stem_ooreen(invoer):
    assert insertion_sort(invoer) == merge_sort(invoer)


# ---------------------------------------------------------------------------
# Randgevalle
# ---------------------------------------------------------------------------

def test_randgevalle_leeg_en_een():
    """'n Leë lys en 'n lys van een item bly soos hulle is."""
    assert insertion_sort([]) == []
    assert merge_sort([]) == []
    assert insertion_sort(["MAIN-G-ENT"]) == ["MAIN-G-ENT"]
    assert merge_sort(["MAIN-G-ENT"]) == ["MAIN-G-ENT"]


def test_invoerlys_bly_onveranderd():
    """
    Albei funksies gee 'n nuwe lys terug en verander nooit die invoer nie.
    """
    oorspronklik = [3, 1, 2]
    kopie_om_te_vergelyk = [3, 1, 2]

    insertion_sort(oorspronklik)
    assert oorspronklik == kopie_om_te_vergelyk

    merge_sort(oorspronklik)
    assert oorspronklik == kopie_om_te_vergelyk


def test_groot_lys():
    """
    'n Groter, herhaalbare lys om te wys die algoritmes bly op skaal.
    """
    groot = [(i * 7919) % 1000 for i in range(500)]

    assert is_korrek_gesorteer(groot, insertion_sort(groot))
    assert is_korrek_gesorteer(groot, merge_sort(groot))
    assert insertion_sort(groot) == merge_sort(groot)


# ---------------------------------------------------------------------------
# Stabiliteit
# ---------------------------------------------------------------------------
HERHAALDE_ETIKETTE = [
    {"node_id": "A1", "etiket": "Hysbak"},
    {"node_id": "B2", "etiket": "Apteek"},
    {"node_id": "C3", "etiket": "Hysbak"},
    {"node_id": "D4", "etiket": "Apteek"},
    {"node_id": "E5", "etiket": "Hysbak"},
]


def test_insertion_sort_is_stabiel():
    resultaat = insertion_sort(HERHAALDE_ETIKETTE, sleutel="etiket")
    assert [n["node_id"] for n in resultaat] == ["B2", "D4", "A1", "C3", "E5"]


def test_merge_sort_is_stabiel():
    resultaat = merge_sort(HERHAALDE_ETIKETTE, sleutel="etiket")
    assert [n["node_id"] for n in resultaat] == ["B2", "D4", "A1", "C3", "E5"]


def test_stabiliteit_bo_die_drempel():
    """
    Stabiliteit geld ook wanneer die lys groot genoeg is dat die rekursie
    werklik gebruik word.
    """
    # 60 items met net drie verskillende sleutels, elk met 'n oplopende
    # volgnommer. Na sortering moet die volgnommers binne elke sleutelgroep
    # nog oplopend wees.
    items = [{"sleutel": i % 3, "volgnommer": i} for i in range(60)]
    resultaat = merge_sort(items, sleutel="sleutel")

    for groep in (0, 1, 2):
        nommers = [x["volgnommer"] for x in resultaat if x["sleutel"] == groep]
        assert nommers == list(range(groep, 60, 3))


# ---------------------------------------------------------------------------
# Die sleutel-parameter in al sy vorme
# ---------------------------------------------------------------------------

GEBOUE = [
    {"gebou_id": "SYGEBOU", "naam": "Sygebou"},
    {"gebou_id": "MAIN",    "naam": "Main Hospitaal Gebou"},
]

VLOERE = [
    {"vloer_id": "MAIN-2",    "gebou_id": "MAIN",    "level_nommer": 2},
    {"vloer_id": "SYGEBOU-G", "gebou_id": "SYGEBOU", "level_nommer": 0},
    {"vloer_id": "MAIN-G",    "gebou_id": "MAIN",    "level_nommer": 0},
    {"vloer_id": "SYGEBOU-1", "gebou_id": "SYGEBOU", "level_nommer": 1},
    {"vloer_id": "MAIN-1",    "gebou_id": "MAIN",    "level_nommer": 1},
]


def test_sleutel_is_none():
    """Sonder sleutel is die item sy eie sleutel."""
    assert insertion_sort([3, 1, 2]) == [1, 2, 3]


def test_sleutel_is_veldnaam():
    """'n Teksnaam sorteer op daardie veld van elke woordeboek."""
    resultaat = insertion_sort(GEBOUE, sleutel="naam")
    assert [g["gebou_id"] for g in resultaat] == ["MAIN", "SYGEBOU"]


def test_sleutel_is_tuple_van_velde():
    """
    sleutel=('gebou_id', 'level_nommer') vervang
    'ORDER BY gebou_id, level_nommer' presies.

    Eers al die MAIN-vloere van vlak 0 tot 2, dan al die SYGEBOU-vloere.
    """
    resultaat = insertion_sort(VLOERE, sleutel=("gebou_id", "level_nommer"))
    assert [v["vloer_id"] for v in resultaat] == [
        "MAIN-G", "MAIN-1", "MAIN-2", "SYGEBOU-G", "SYGEBOU-1",
    ]


def test_sleutel_is_funksie():
    resultaat = merge_sort(GEBOUE, sleutel=lambda g: len(g["naam"]))
    assert [g["gebou_id"] for g in resultaat] == ["SYGEBOU", "MAIN"]


def test_sleutel_werk_met_woordeboeke_wat_nie_vergelykbaar_is_nie():
    """
    Kan nie met < of > vergelyk word nie. Die algoritmes moet
    net die sleutel vergelyk. Verkeerd = Python gooi 'n TypeError
    """
    items = [{"n": 2}, {"n": 1}, {"n": 2}, {"n": 1}]   # twee pare gelyke sleutels
    assert [x["n"] for x in insertion_sort(items, sleutel="n")] == [1, 1, 2, 2]
    assert [x["n"] for x in merge_sort(items, sleutel="n")] == [1, 1, 2, 2]


# ---------------------------------------------------------------------------
# Die hibriede drumpel
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("drempel", [0, 1, 2, 5, 12, 50, 1000])
def test_drempel_verander_nie_die_uitkoms_nie(drempel):
    """
    Die drumpel word gebruik spoed-optimering, nie deel van die logika nie.

    By drempel=0 word suiwer saamsmeltsortering gebruik; by drempel=1000 word
    alles deur invoegsortering gedoen. Die antwoord moet in elke geval
    identies wees
    """
    invoer = [(i * 37) % 60 for i in range(60)]
    assert merge_sort(invoer, drempel=drempel) == merge_sort(invoer, drempel=12)


# ---------------------------------------------------------------------------
# Werklike hospitaaldata
# ---------------------------------------------------------------------------

def test_hospitaal_node_ids_word_gesorteer():
    node_ids = ["MAIN-2-ELV", "MAIN-G-ELV", "SYGEBOU-1-ELV", "MAIN-1-ELV", "SYGEBOU-G-ELV"]
    assert merge_sort(node_ids) == [
        "MAIN-1-ELV", "MAIN-2-ELV", "MAIN-G-ELV", "SYGEBOU-1-ELV", "SYGEBOU-G-ELV",
    ]


def test_hospitaal_etikette_word_gesorteer():
    nodes = [
        {"node_id": "MAIN-G-ENT", "etiket": "Hoof Publiek Ingang"},
        {"node_id": "MAIN-G-ER",  "etiket": "Nooddienste"},
        {"node_id": "MAIN-G-ELV", "etiket": "Hysbak Grond"},
        {"node_id": "MAIN-G-STA", "etiket": "Trappe Grond"},
    ]
    resultaat = merge_sort(nodes, sleutel="etiket")
    assert [n["etiket"] for n in resultaat] == [
        "Hoof Publiek Ingang", "Hysbak Grond", "Nooddienste", "Trappe Grond",
    ]
