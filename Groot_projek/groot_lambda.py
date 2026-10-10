"""Stap 3a: lambda teenoor def teenoor inline, op die projek se eie formules.

Wat vergelyk word
-----------------
  • BEREKEN_AFSTAND en BEREKEN_GEWIG uit HospitaalGrafiek.py (die twee benoemde
    lambda's), elk as:  lambda (die projek se eie)  |  def  |  inline in die lus.
  • 'n Sorteersleutel as lambda, def en operator.itemgetter, deur die projek se
    eie merge_sort() (Sorteer.py), plus Python se sorted() as verwysing.

Eerlike verwagting: 'n lambda en 'n def met dieselfde inhoud kompileer na
dieselfde greepkode, dus is die verskil tussen hulle ruis. Die werklike
koste is die FUNKSIE-AANROEP self; inline spaar dit. Die tellings (aantal
aanroepe) is identies vir elke variant; net die tye verskil.
Niks in die bestaande lêers word verander nie.
"""

import math
import operator
import random

from groot_paaie import maak_hoofprojek_beskikbaar

maak_hoofprojek_beskikbaar()

from HospitaalGrafiek import BEREKEN_AFSTAND, BEREKEN_GEWIG
from groot_meet import meet
from Sorteer import merge_sort


def afstand_def(pos_a, pos_b):
    """Dieselfde formule as BEREKEN_AFSTAND, maar as gewone def."""
    return math.hypot(pos_a[0] - pos_b[0], pos_a[1] - pos_b[1])


def gewig_def(basis_gewig_s, wag_penalty_s):
    """Dieselfde formule as BEREKEN_GEWIG, maar as gewone def."""
    return float(basis_gewig_s) + float(wag_penalty_s)


def sleutel_def(kant):
    """Dieselfde sleutel as lambda kant: kant[2]."""
    return kant[2]


# ---------------------------------------------------------------------------
# Toetsdata (herhaalbaar)
# ---------------------------------------------------------------------------

def maak_data(n, saad=11):
    """n posisiepare, n (basis, wag)-pare en n kante (a, b, gewig) om te sorteer."""
    rng = random.Random(saad)
    posisies = [((rng.uniform(0, 500), rng.uniform(0, 500)),
                 (rng.uniform(0, 500), rng.uniform(0, 500))) for _ in range(n)]
    gewigte = [(rng.uniform(1, 40), rng.choice([0, 0, 0, 25])) for _ in range(n)]
    kante = [(f"N{i}", f"N{i + 1}", rng.uniform(1, 100)) for i in range(n)]
    return posisies, gewigte, kante


# ---------------------------------------------------------------------------
# Varianttabelle: naam -> funksie(data) wat 'n lys resultate gee
# ---------------------------------------------------------------------------

def _afstand_lambda(d):
    f = BEREKEN_AFSTAND
    return [f(a, b) for a, b in d[0]]


def _afstand_def(d):
    f = afstand_def
    return [f(a, b) for a, b in d[0]]


def _afstand_inline(d):
    hypot = math.hypot
    return [hypot(a[0] - b[0], a[1] - b[1]) for a, b in d[0]]


def _gewig_lambda(d):
    f = BEREKEN_GEWIG
    return [f(b, w) for b, w in d[1]]


def _gewig_def(d):
    f = gewig_def
    return [f(b, w) for b, w in d[1]]


def _gewig_inline(d):
    return [float(b) + float(w) for b, w in d[1]]


def _sorteer_lambda(d):
    return merge_sort(d[2], lambda kant: kant[2])


def _sorteer_def(d):
    return merge_sort(d[2], sleutel_def)


def _sorteer_itemgetter(d):
    return merge_sort(d[2], operator.itemgetter(2))


def _sorteer_ingebou(d):
    return sorted(d[2], key=lambda kant: kant[2])


EKSPERIMENTE = {
    "afstand": {
        "lambda (BEREKEN_AFSTAND)": _afstand_lambda,
        "def": _afstand_def,
        "inline": _afstand_inline,
    },
    "gewig": {
        "lambda (BEREKEN_GEWIG)": _gewig_lambda,
        "def": _gewig_def,
        "inline": _gewig_inline,
    },
    "sorteersleutel (merge_sort)": {
        "lambda": _sorteer_lambda,
        "def": _sorteer_def,
        "operator.itemgetter": _sorteer_itemgetter,
        "sorted() + lambda (verwysing)": _sorteer_ingebou,
    },
}


def lambda_eksperiment(groottes, herhalings=5, volg=None):
    """Meet elke variant op elke grootte en kontroleer dat al die variante dieselfde uitkoms gee.

    'aanroepe' is die aantal formule-/sleutelaanroepe: dieselfde vir elke variant
    van een eksperiment. Gee 'n lys rye met 'eksperiment', 'variant', 'n', tye.
    """
    rye = []
    for n in sorted(groottes):
        data = maak_data(n)
        for eksperiment, variante in EKSPERIMENTE.items():
            verwysing = None
            for naam, funksie in variante.items():
                stats, uit = meet(lambda f=funksie: f(data), herhalings, begroting_s=3.0)
                if verwysing is None:
                    verwysing = uit
                elif not _stem_ooreen(uit, verwysing):
                    raise RuntimeError(f"{eksperiment}/{naam} gee 'n ander uitkoms (n={n}).")
                ry = {"eksperiment": eksperiment, "variant": naam, "n": n,
                      "aanroepe": n, "status": "ok", **stats}
                rye.append(ry)
                if volg:
                    volg(ry)
    return rye


def _stem_ooreen(a, b):
    """Getalle word met 'n klein rekenfout vergelyk; ander waardes presies."""
    if len(a) != len(b):
        return False
    return all(math.isclose(x, y, rel_tol=1e-12) if isinstance(x, float) else x == y
               for x, y in zip(a, b))
