"""2-4-boom: invoeging, soek en geordende deurloop in geheue.

Elke nodus bevat hoogstens drie sleutels. Alle blare bly ewe diep deur
vol kinders te verdeel voordat invoeging verder daarin afbeweeg.
"""

from dataclasses import dataclass, field

# 'n 2-4-boom se nodus het 1 tot 3 sleutels (dus 2 tot 4 kinders).
# Met 3 sleutels is 'n nodus "vol" en moet dit verdeel word.
MAKS_SLEUTELS = 3

# Die metadata-velde waarin soek_metadata() na teks soek (buiten "etiket").
METADATA_VELDE = ("node_id", "tipe_kode", "gebou_naam", "vloer_naam")


@dataclass
class BoomNodus:
    """Bewaar 'n nodus se sleutels, ooreenstemmende waardes en kinders."""

    sleutels: list = field(default_factory=list)
    waardes: list = field(default_factory=list)
    kinders: list = field(default_factory=list)

    def vind_indeks(self, sleutel):
        """Gee die indeks van die eerste sleutel wat minstens so groot is.

        Gee len(self.sleutels) as alle sleutels kleiner is. Dieselfde getal
        is ook die indeks van die kind waarin 'sleutel' kan voorkom.
        """
        i = 0
        while i < len(self.sleutels) and sleutel > self.sleutels[i]:
            i += 1
        return i


def _bevat(bestemming, veld, term):
    """Kyk of die term (reeds casefold) in een veld van die bestemming voorkom."""
    # "or ''" hanteer velde wat None is, bv. 'n nodus sonder beperkte_groep.
    return term in (bestemming.get(veld) or "").casefold()


class Boom24:
    """Selfbalanserende 2-4-boom met geordende sleutels en gekoppelde waardes."""

    def __init__(self):
        self.wortel = BoomNodus()

    def soek(self, sleutel):
        """Gee die sleutel se waarde terug, of None wanneer dit ontbreek."""
        nodus = self.wortel

        while True:
            # Vind die eerste sleutel wat minstens so groot is.
            i = nodus.vind_indeks(sleutel)

            # Sleutel gevind: gee die ooreenstemmende waarde terug.
            if i < len(nodus.sleutels) and sleutel == nodus.sleutels[i]:
                return nodus.waardes[i]

            # By 'n blaar sonder 'n passing eindig die soektog.
            if not nodus.kinders:
                return None

            # Volg die kind waarin die sleutel kan voorkom.
            nodus = nodus.kinders[i]

    def verdeel_kind(self, ouer, indeks):
        """Verdeel 'n vol kind en skuif sy middelste sleutel na die ouer."""
        vol_kind = ouer.kinders[indeks]

        # Die kind moet vol wees en die ouer moet plek hê.
        if len(vol_kind.sleutels) != MAKS_SLEUTELS:
            raise ValueError("Die kind moet presies 3 sleutels hê.")

        if len(ouer.sleutels) >= MAKS_SLEUTELS:
            raise ValueError("Verdeel eers die vol ouer.")

        # Maak 'n linkerkind met die kleinste sleutel.
        links = BoomNodus(
            sleutels=vol_kind.sleutels[:1],
            waardes=vol_kind.waardes[:1],
            kinders=vol_kind.kinders[:2],
        )

        # Maak 'n regterkind met die grootste sleutel.
        regs = BoomNodus(
            sleutels=vol_kind.sleutels[2:],
            waardes=vol_kind.waardes[2:],
            kinders=vol_kind.kinders[2:],
        )

        # Skuif die middelste sleutel en sy waarde na die ouer.
        ouer.sleutels.insert(indeks, vol_kind.sleutels[1])
        ouer.waardes.insert(indeks, vol_kind.waardes[1])

        # Vervang die oorspronklike kind met die twee nuwe kinders.
        ouer.kinders[indeks:indeks + 1] = [links, regs]

    def voeg_in(self, sleutel, waarde):
        """Voeg 'n sleutel/waarde by, of vervang 'n bestaande sleutel se waarde.

        O(log n) sleutelvergelykings; sleutels moet onderling vergelykbaar wees.
        """
        # 'n Vol wortel word verdeel onder 'n nuwe wortel; dit is die enigste
        # manier waarop die boom hoër word, en alle blare skuif saam een vlak af.
        if len(self.wortel.sleutels) == MAKS_SLEUTELS:
            self.wortel = BoomNodus(kinders=[self.wortel])
            self.verdeel_kind(self.wortel, 0)

        nodus = self.wortel
        while True:
            i = nodus.vind_indeks(sleutel)

            # Bestaande sleutel: vervang net die waarde.
            if i < len(nodus.sleutels) and sleutel == nodus.sleutels[i]:
                nodus.waardes[i] = waarde
                return

            # Blaar bereik: daar is gewaarborg plek, want ons het vol nodusse
            # op pad hierheen reeds verdeel.
            if not nodus.kinders:
                nodus.sleutels.insert(i, sleutel)
                nodus.waardes.insert(i, waarde)
                return

            # Die huidige nodus het plek vir 'n sleutel uit 'n vol kind.
            if len(nodus.kinders[i].sleutels) == MAKS_SLEUTELS:
                self.verdeel_kind(nodus, i)
                # Die middelste sleutel van die kind is nou in hierdie nodus.
                if sleutel == nodus.sleutels[i]:
                    nodus.waardes[i] = waarde
                    return
                if sleutel > nodus.sleutels[i]:
                    i += 1

            nodus = nodus.kinders[i]

    def in_volgorde(self):
        """Gee (sleutel, waarde)-pare in sleutelvolgorde terug. O(n) vir alles."""
        pare = []
        self._deurloop(self.wortel, pare)
        return pare

    def _deurloop(self, nodus, pare):
        """Voeg 'n nodus se sleutels en sy kinders se sleutels links na regs by 'pare'."""
        for i, sleutel in enumerate(nodus.sleutels):
            # Eers alles in die kind links van hierdie sleutel...
            if nodus.kinders:
                self._deurloop(nodus.kinders[i], pare)
            # ...dan die sleutel self.
            pare.append((sleutel, nodus.waardes[i]))
        # Die laaste kind het geen sleutel regs van hom nie, daarom hier apart.
        if nodus.kinders:
            self._deurloop(nodus.kinders[-1], pare)

    def soek_metadata(self, teks, limiet=20):
        """Soek letterlike teks enige plek in bestemmingsmetadata.

        Sleutels is (naam.strip().casefold(), node_id). Naamtreffers kom
        eerste; ander metadata-treffers volg. Elke groep bly in boomvolgorde.
        Die leë term pas by alle bestemmings. % en _ is gewone karakters.
        Hoogstens n bestemmings word ondersoek: O(n), buiten teksvergelykings.
        """
        if limiet < 0:
            raise ValueError("Die limiet mag nie negatief wees nie.")
        if limiet == 0:
            return []
        term = teks.strip().casefold()
        alle_pare = self.in_volgorde()

        # Eerste lus: bestemmings waarvan die naam die term bevat.
        naamtreffers = []
        for _, bestemming in alle_pare:
            if _bevat(bestemming, "etiket", term):
                naamtreffers.append(bestemming)

        # Tweede lus: ander treffers, dws die term is in 'n ander veld
        # maar NIE in die naam nie (anders sou hulle dubbel getel word).
        ander_treffers = []
        for _, bestemming in alle_pare:
            if _bevat(bestemming, "etiket", term):
                continue
            for veld in METADATA_VELDE:
                if _bevat(bestemming, veld, term):
                    ander_treffers.append(bestemming)
                    break

        # Naamtreffers eerste, en dan sny ons by die limiet af.
        return (naamtreffers + ander_treffers)[:limiet]

    def valideer(self):
        """Kontroleer al die boomreëls; gee True of gooi ValueError. O(n)."""
        blaardieptes = set()
        besoek = set()
        # Al die sleutels in die volgorde waarin 'n in-orde deurloop hulle sien.
        alle_sleutels = []

        def kontroleer(nodus, diepte):
            if id(nodus) in besoek:
                raise ValueError("'n Nodus word hergebruik of vorm 'n siklus.")
            besoek.add(id(nodus))
            aantal = len(nodus.sleutels)

            # 'n Heeltemal leë boom het 'n leë wortel sonder kinders.
            if aantal == 0 and nodus is self.wortel and not nodus.kinders:
                if nodus.waardes:
                    raise ValueError("Die leë wortel mag geen waardes hê nie.")
                return

            if not 1 <= aantal <= MAKS_SLEUTELS or len(nodus.waardes) != aantal:
                raise ValueError("Elke nodus benodig 1–3 sleutels met hul waardes.")

            if not nodus.kinders:
                blaardieptes.add(diepte)
                alle_sleutels.extend(nodus.sleutels)
                return

            if len(nodus.kinders) != aantal + 1:
                raise ValueError("'n Interne nodus benodig een meer kind as sleutels.")

            # Kind i, dan sleutel i, soos in in_volgorde().
            for i, kind in enumerate(nodus.kinders):
                kontroleer(kind, diepte + 1)
                if i < aantal:
                    alle_sleutels.append(nodus.sleutels[i])

        kontroleer(self.wortel, 0)

        # Een kontrole vervang die ou onder-/bogrens-parameters: as die sleutels
        # in deurloopvolgorde streng styg, is elke nodus se sleutels reg
        # verhoudend tot sy hele subboom.
        for vorige, volgende in zip(alle_sleutels, alle_sleutels[1:]):
            if not vorige < volgende:
                raise ValueError("Sleutels is nie in streng stygende volgorde nie.")

        if len(blaardieptes) > 1:
            raise ValueError("Alle blare moet ewe diep wees.")
        return True
