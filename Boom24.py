"""2-4-boom: invoeging, soek en geordende deurloop in geheue.

Elke nodus bevat hoogstens drie sleutels. Alle blare bly ewe diep deur
vol kinders te verdeel voordat invoeging verder daarin afbeweeg.
"""

from dataclasses import dataclass, field


@dataclass
class BoomNodus:
    sleutels: list = field(default_factory=list)
    waardes: list = field(default_factory=list)
    kinders: list = field(default_factory=list)


class Boom24:
    def __init__(self):
        self.wortel = BoomNodus()

    def soek(self, sleutel):
        nodus = self.wortel

        while True:
            i = 0

            # Vind die eerste sleutel wat minstens so groot is.
            while (
                i < len(nodus.sleutels)
                and sleutel > nodus.sleutels[i]
            ):
                i += 1

            # Sleutel gevind: gee die ooreenstemmende waarde terug.
            if (
                i < len(nodus.sleutels)
                and sleutel == nodus.sleutels[i]
            ):
                return nodus.waardes[i]

            # By 'n blaar sonder 'n passing eindig die soektog.
            if not nodus.kinders:
                return None

            # Volg die kind waarin die sleutel kan voorkom.
            nodus = nodus.kinders[i]

    def verdeel_kind(self, ouer, indeks):
        vol_kind = ouer.kinders[indeks]

        # Die kind moet vol wees en die ouer moet plek hê.
        if len(vol_kind.sleutels) != 3:
            raise ValueError("Die kind moet presies 3 sleutels hê.")

        if len(ouer.sleutels) >= 3:
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
        if len(self.wortel.sleutels) == 3:
            self.wortel = BoomNodus(kinders=[self.wortel])
            self.verdeel_kind(self.wortel, 0)

        nodus = self.wortel
        while True:
            i = 0
            while i < len(nodus.sleutels) and sleutel > nodus.sleutels[i]:
                i += 1

            if i < len(nodus.sleutels) and sleutel == nodus.sleutels[i]:
                nodus.waardes[i] = waarde
                return

            if not nodus.kinders:
                nodus.sleutels.insert(i, sleutel)
                nodus.waardes.insert(i, waarde)
                return

            # Die huidige nodus het plek vir 'n sleutel uit 'n vol kind.
            if len(nodus.kinders[i].sleutels) == 3:
                self.verdeel_kind(nodus, i)
                if sleutel == nodus.sleutels[i]:
                    nodus.waardes[i] = waarde
                    return
                if sleutel > nodus.sleutels[i]:
                    i += 1

            nodus = nodus.kinders[i]

    def in_volgorde(self):
        """Lewer (sleutel, waarde)-pare in sleutelvolgorde. O(n) vir alles."""
        def deurloop(nodus):
            for i, sleutel in enumerate(nodus.sleutels):
                if nodus.kinders:
                    yield from deurloop(nodus.kinders[i])
                yield sleutel, nodus.waardes[i]
            if nodus.kinders:
                yield from deurloop(nodus.kinders[-1])

        yield from deurloop(self.wortel)

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
        naamtreffers = []
        ander_treffers = []
        velde = ("node_id", "tipe_kode", "gebou_naam", "vloer_naam")
        for _, bestemming in self.in_volgorde():
            if term in (bestemming.get("etiket") or "").casefold():
                naamtreffers.append(bestemming)
                if len(naamtreffers) == limiet:
                    break
            elif len(ander_treffers) < limiet and any(
                term in (bestemming.get(veld) or "").casefold() for veld in velde
            ):
                ander_treffers.append(bestemming)
        return (naamtreffers + ander_treffers)[:limiet]

    def valideer(self):
        """Kontroleer al die boomreëls; gee True of gooi ValueError. O(n)."""
        blaardieptes = set()
        besoek = set()

        def kontroleer(nodus, onder, bo, diepte):
            if id(nodus) in besoek:
                raise ValueError("'n Nodus word hergebruik of vorm 'n siklus.")
            besoek.add(id(nodus))
            aantal = len(nodus.sleutels)
            if aantal == 0 and nodus is self.wortel and not nodus.kinders:
                if nodus.waardes:
                    raise ValueError("Die leë wortel mag geen waardes hê nie.")
                return
            if not 1 <= aantal <= 3 or len(nodus.waardes) != aantal:
                raise ValueError("Elke nodus benodig 1–3 sleutels met hul waardes.")
            vorige = onder
            for sleutel in nodus.sleutels:
                if vorige is not None and not vorige < sleutel:
                    raise ValueError("Sleutels is buite volgorde of hul ondergrens.")
                if bo is not None and not sleutel < bo:
                    raise ValueError("'n Sleutel oorskry sy subboom se bogrens.")
                vorige = sleutel
            if not nodus.kinders:
                blaardieptes.add(diepte)
                return
            if len(nodus.kinders) != aantal + 1:
                raise ValueError("'n Interne nodus benodig een meer kind as sleutels.")
            grense = [onder] + nodus.sleutels + [bo]
            for i, kind in enumerate(nodus.kinders):
                kontroleer(kind, grense[i], grense[i + 1], diepte + 1)

        kontroleer(self.wortel, None, None, 0)
        if len(blaardieptes) > 1:
            raise ValueError("Alle blare moet ewe diep wees.")
        return True
