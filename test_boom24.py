"""Toetse vir die 2-4-boom: invoeging, soek, metadata-soektog en die valideerder."""

import random

import pytest

from Boom24 import Boom24, BoomNodus


@pytest.mark.parametrize("volgorde", ["stygend", "dalend", "deurmekaar"])
def test_invoeging_balanseer_en_behou_waardes(volgorde):
    """Invoeging in stygende, dalende en deurmekaar volgorde hou die boom geldig; herinvoeging vervang net die waarde."""
    sleutels = list(range(120))
    if volgorde == "dalend":
        sleutels.reverse()
    elif volgorde == "deurmekaar":
        random.Random(24).shuffle(sleutels)
    boom = Boom24()
    verwag = {}
    for sleutel in sleutels:
        boom.voeg_in(sleutel, str(sleutel))
        verwag[sleutel] = str(sleutel)
        assert boom.valideer()
        assert list(boom.in_volgorde()) == sorted(verwag.items())
    for sleutel in sleutels:
        assert boom.soek(sleutel) == str(sleutel)
        boom.voeg_in(sleutel, None)
        assert boom.valideer()
    assert list(boom.in_volgorde()) == [(i, None) for i in range(120)]
    assert boom.soek(-1) is None
    assert boom.soek(999) is None


def test_lee_boom_en_onafhanklike_nodusse():
    """'n Leë boom is geldig en soek niks; elke nodus kry sy eie lyste (geen gedeelde verstekwaardes nie)."""
    boom = Boom24()
    assert boom.valideer()
    assert boom.soek(1) is None
    assert list(boom.in_volgorde()) == []
    assert boom.soek_metadata("") == []
    eerste, tweede = BoomNodus(), BoomNodus()
    for veld in ("sleutels", "waardes", "kinders"):
        assert getattr(eerste, veld) is not getattr(tweede, veld)


def test_metadata_duplikaatname_unicode_en_limiete():
    """soek_metadata hanteer duplikaatname, hoof-/kleinletters (casefold), spasies, die limiet en 'n negatiewe limiet."""
    boom = Boom24()
    data = [("Saal A", "S"), ("Radiologie", "B"), ("Ontvangs", "O"),
            ("Radiologie", "A"), ("Radiologie-ontvangs", "C"),
            ("Straße", "D"), ("Radiologie\U0010ffffx", "U")]
    for naam, node_id in data:
        boom.voeg_in((naam.casefold(), node_id), {"etiket": naam, "node_id": node_id})
    def ids(teks, limiet=20):
        return [item["node_id"] for item in boom.soek_metadata(teks, limiet)]
    assert ids("  RAD  ") == ["A", "B", "C", "U"]
    assert ids("rad", 2) == ["A", "B"]
    assert ids("rad", 0) == []
    assert ids("STRASS") == ["D"]
    assert ids("diologie") == ["A", "B", "C", "U"]
    assert ids("zzz") == []
    assert ids("", 2) == ["O", "A"]
    with pytest.raises(ValueError):
        boom.soek_metadata("rad", -1)


@pytest.mark.parametrize("veld", ["etiket", "node_id", "tipe_kode", "gebou_naam", "vloer_naam"])
def test_metadata_soek_binne_elke_veld(veld):
    """Elke metadata-veld word deursoek, % en _ is letterlike karakters, en die hele term moet binne een veld pas."""
    boom = Boom24()
    item = {"etiket": "Ontvangs", "node_id": "N1", "tipe_kode": None}
    item[veld] = "Voor_TREF%Agter"
    boom.voeg_in((item["etiket"].casefold(), item["node_id"]), item)
    assert boom.soek_metadata("  tReF%  ") == [item]
    assert boom.soek_metadata("_") == [item]
    assert boom.soek_metadata("TREF_") == []
    assert boom.soek_metadata("%Agter") == [item]
    # Die hele term moet binne een veld voorkom, nie oor veldgrense nie.
    assert boom.soek_metadata("Ontvangs N1") == []


def test_naamtreffers_kom_voor_metadata_selfs_met_limiet():
    """Naamtreffers kom altyd voor ander treffers, ook wanneer die limiet dit sou afsny."""
    boom = Boom24()
    for naam in ["A", "B", "Z Kliniek", "Y Kliniek"]:
        item = {"etiket": naam, "node_id": naam, "gebou_naam": "Kliniek"}
        boom.voeg_in((naam.casefold(), naam), item)
    assert [r["etiket"] for r in boom.soek_metadata("kliniek", 2)] == ["Y Kliniek", "Z Kliniek"]
    assert [r["etiket"] for r in boom.soek_metadata("kliniek", 4)] == ["Y Kliniek", "Z Kliniek", "A", "B"]


@pytest.mark.parametrize("fout", ["volgorde", "waardes", "kindtelling", "grense", "diepte"])
def test_valideerder_verwerp_ongeldige_bome(fout):
    """valideer() gooi ValueError by elke reëlbreuk: volgorde, waardes, kindtelling, sleutelgrense en blaardiepte."""
    boom = Boom24()
    boom.wortel = BoomNodus([20], [20], [BoomNodus([10], [10]), BoomNodus([30], [30])])
    if fout == "volgorde":
        boom.wortel.kinders[0] = BoomNodus([10, 5], [10, 5])
    elif fout == "waardes":
        boom.wortel.waardes = []
    elif fout == "kindtelling":
        boom.wortel.kinders.pop()
    elif fout == "grense":
        boom.wortel.kinders[0].sleutels = [25]
    else:  # "diepte": een kind het blare, die ander nie
        boom.wortel.kinders[0].kinders = [BoomNodus([5], [5]), BoomNodus([15], [15])]
    with pytest.raises(ValueError):
        boom.valideer()
