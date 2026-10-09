"""2-4-boom: invoeging, soek en geordende deurloop in geheue.

Elke nodus het 1 tot 3 sleutels en dus 2 tot 4 kinders. Alle blare bly
ewe diep, omdat 'n vol nodus verdeel word voordat ons daarin afgaan.
"""

from dataclasses import dataclass, field

# 'n Nodus het 1 tot 3 sleutels (dus 2 tot 4 kinders).
# Met 3 sleutels is 'n nodus "vol" en moet dit verdeel word.
MAKS_SLEUTELS = 3

# Velde waarin soek_metadata() soek, benewens "etiket".
METADATA_VELDE = ("node_id", "tipe_kode", "gebou_naam", "vloer_naam")


@dataclass
class BoomNodus:
    """'n Nodus met sleutels, die waardes wat by hulle hoort, en kinders."""

    sleutels: list = field(default_factory=list)
    waardes: list = field(default_factory=list)   # waardes[i] hoort by sleutels[i]
    kinders: list = field(default_factory=list)   # leeg by 'n blaar

    def vind_indeks(self, sleutel):
        """Gee die indeks van die eerste sleutel wat minstens so groot is.

        Dieselfde getal is ook die indeks van die kind waarin 'sleutel'
        kan voorkom (len(sleutels) as alle sleutels kleiner is).
        """
        i = 0
        while i < len(self.sleutels) and sleutel > self.sleutels[i]:
            i += 1
        return i


class Boom24:
    """Selfbalanserende 2-4-boom met geordende sleutels en gekoppelde waardes."""

    def __init__(self):
        self.wortel = BoomNodus()

    def soek(self, sleutel):
        """Gee die waarde by die sleutel, of None as dit ontbreek."""
        nodus = self.wortel
        while True:
            i = nodus.vind_indeks(sleutel)

            # Sleutel gevind in hierdie nodus.
            if i < len(nodus.sleutels) and sleutel == nodus.sleutels[i]:
                return nodus.waardes[i]

            # By 'n blaar is daar nêrens meer om te soek nie.
            if not nodus.kinders:
                return None

            # Gaan af in die kind waarin die sleutel kan voorkom.
            nodus = nodus.kinders[i]

    def verdeel_kind(self, ouer, indeks):
        """Verdeel 'n vol kind; sy middelste sleutel skuif op na die ouer.

        Die ouer het plek, want voeg_in() verdeel altyd eers van bo na onder.
        """
        vol = ouer.kinders[indeks]

        # Kleinste sleutel links, grootste sleutel regs (die kinders word ook gedeel).
        links = BoomNodus(vol.sleutels[:1], vol.waardes[:1], vol.kinders[:2])
        regs = BoomNodus(vol.sleutels[2:], vol.waardes[2:], vol.kinders[2:])

        # Die middelste sleutel (en sy waarde) gaan op na die ouer.
        ouer.sleutels.insert(indeks, vol.sleutels[1])
        ouer.waardes.insert(indeks, vol.waardes[1])

        # Die een vol kind word vervang deur die twee nuwes.
        ouer.kinders[indeks:indeks + 1] = [links, regs]

    def voeg_in(self, sleutel, waarde):
        """Voeg 'n sleutel/waarde by, of vervang die waarde as die sleutel bestaan."""
        # 'n Vol wortel word onder 'n nuwe wortel verdeel. Dit is die enigste
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

            # Blaar bereik: daar is gewaarborg plek, want ons het alle vol
            # nodusse op pad hierheen reeds verdeel.
            if not nodus.kinders:
                nodus.sleutels.insert(i, sleutel)
                nodus.waardes.insert(i, waarde)
                return

            # Verdeel 'n vol kind voordat ons daarin afgaan.
            if len(nodus.kinders[i].sleutels) == MAKS_SLEUTELS:
                self.verdeel_kind(nodus, i)
                # Die kind se middelste sleutel is nou in hierdie nodus.
                if sleutel == nodus.sleutels[i]:
                    nodus.waardes[i] = waarde
                    return
                if sleutel > nodus.sleutels[i]:
                    i += 1

            nodus = nodus.kinders[i]

    def in_volgorde(self):
        """Gee (sleutel, waarde)-pare in sleutelvolgorde terug."""
        pare = []
        self._deurloop(self.wortel, pare)
        return pare

    def _deurloop(self, nodus, pare):
        """In-orde deurloop: kind links, sleutel, kind links, sleutel, ... laaste kind."""
        for i, sleutel in enumerate(nodus.sleutels):
            if nodus.kinders:
                self._deurloop(nodus.kinders[i], pare)   # Alles links van die sleutel.
            pare.append((sleutel, nodus.waardes[i]))
        if nodus.kinders:
            self._deurloop(nodus.kinders[-1], pare)      # Laaste kind, regs van alles.

    def soek_metadata(self, teks, limiet=20):
        """Soek letterlike deelteks in die bestemmings se metadata.

        Naamtreffers kom eerste, dan treffers in ander velde; elke groep bly
        in boomvolgorde. Die leë term pas by almal. Dit kos O(n): die boom
        help hier slegs met sy gesorteerde volgorde, nie met die soektog self nie.
        """
        if limiet < 0:
            raise ValueError("Die limiet mag nie negatief wees nie.")

        term = teks.strip().casefold()
        naam_treffers = []
        ander_treffers = []

        # Een deurloop: "or ''" hanteer velde wat None is (bv. beperkte_groep).
        for _, bestemming in self.in_volgorde():
            if term in (bestemming.get("etiket") or "").casefold():
                naam_treffers.append(bestemming)
            elif any(term in (bestemming.get(veld) or "").casefold()
                     for veld in METADATA_VELDE):
                ander_treffers.append(bestemming)

        # Naamtreffers eerste, dan sny ons by die limiet af.
        return (naam_treffers + ander_treffers)[:limiet]

    def valideer(self):
        """Kontroleer die boomreëls; gee True of gooi ValueError."""
        # 'n Leë boom is geldig.
        if not self.wortel.sleutels and not self.wortel.kinders:
            return True

        sleutels = []      # Sleutels in deurloopvolgorde.
        dieptes = set()    # Die diepte van elke blaar.

        def kyk(nodus, diepte):
            n = len(nodus.sleutels)

            # Reël 1: 1 tot 3 sleutels, met 'n waarde by elke sleutel.
            if not 1 <= n <= MAKS_SLEUTELS or len(nodus.waardes) != n:
                raise ValueError("Elke nodus benodig 1–3 sleutels met hul waardes.")

            # Blaar: onthou sy diepte en sy sleutels.
            if not nodus.kinders:
                dieptes.add(diepte)
                sleutels.extend(nodus.sleutels)
                return

            # Reël 2: 'n interne nodus het een kind meer as sleutels.
            if len(nodus.kinders) != n + 1:
                raise ValueError("'n Interne nodus benodig een kind meer as sleutels.")

            # Kind i, dan sleutel i, soos in in_volgorde().
            for i, kind in enumerate(nodus.kinders):
                kyk(kind, diepte + 1)
                if i < n:
                    sleutels.append(nodus.sleutels[i])

        kyk(self.wortel, 0)

        # Reël 3: as die sleutels in deurloopvolgorde streng styg, is elke
        # nodus se sleutels reg ten opsigte van sy hele subboom.
        if any(a >= b for a, b in zip(sleutels, sleutels[1:])):
            raise ValueError("Sleutels is nie in streng stygende volgorde nie.")

        # Reël 4: alle blare is ewe diep.
        if len(dieptes) > 1:
            raise ValueError("Alle blare moet ewe diep wees.")
        return True
