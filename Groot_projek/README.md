# Groot datastel-vertoning

'n Aparte vertoning langs die hoofprojek wat dieselfde algoritmes op baie meer
data (ongeveer 2000 nodusse) laat loop, sodat bottelnekke en tydsverskille
duidelik word. Dit vergelyk sortering, Dijkstra en A\* (met verskillende
prioriteitstoue), Kruskal, maksimum vloei en parallelle ontruimingsdekking.

Die vertoning hergebruik `HospitaalGrafiek.py`, `Sorteer.py` en
`mst_en_vloei.py`. `groot_paaie.py` maak hierdie modules ook beskikbaar wanneer
'n stap direk vanuit die hoofprojek of 'n ander werkgids begin word.

## Belangrik: lêernaam-hoofletters

Die lêers voer mekaar met kleinletters in (`from groot_algoritmes import ...`).
Hou die name presies soos in die tabel hieronder, ook die toetslêers, wat met
`test_` moet begin sodat pytest hulle optel. Windows maak nie onderskeid tussen
hoof- en kleinletters nie, maar Linux (en dus Docker) wel.

## Lêers

| Fase | Lêer                                                                         | Doel                                                                                                                                                     |
| ---- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | `groot_algoritmes.py`                                                        | Ligte grafiek in geheue, Dijkstra, A\*, ontruimingskaart vir alle nodusse, Kruskal met verwisselbare sortering, maksimum vloei met superbron en superput |
| 1    | `groot_data.py`                                                              | CSV laai en stoor, en 'n generator vir toetsdata van enige grootte                                                                                       |
| 1    | `groot_stap1.py`                                                             | Loop die kernalgoritmes en druk tellings en bottelnekke                                                                                                  |
| 1    | `test_groot.py`                                                              | Toetse vir fase 1                                                                                                                                        |
| 2    | `groot_tou_variante.py`                                                      | Dijkstra/A\* met drie prioriteitstoue (heapq, woordeboek met `min()`, gesorteerde lys met `bisect`)                                                      |
| 2    | `groot_meet.py`                                                              | Meetbord: herhaalde tye met mediaan, minimum en maksimum, tellings, en 'n tydgrens met oorslaanreël                                                      |
| 2    | `groot_stap2.py`                                                             | Loop die sorteer-, roete- en Kruskal-eksperimente en stoor `groot_resultate.json`                                                                        |
| 2    | `test_groot_meet.py`                                                         | Toetse vir fase 2                                                                                                                                        |
| 3    | `groot_lambda.py`                                                            | Lambda teenoor `def` teenoor inline, op die projek se eie formules en 'n sorteersleutel                                                                  |
| 3    | `groot_parallel.py`                                                          | Skryf die groot grafiek na SQLite (met `Skema.sql`) en vergelyk sekwensiële en parallelle dekking met die projek se eie `HospitaalGrafiek`               |
| 3    | `groot_stap3.py`                                                             | Loop beide fase 3-eksperimente en stoor `groot_resultate_stap3.json`                                                                                     |
| 3    | `test_groot_stap3.py`                                                        | Toetse vir fase 3                                                                                                                                        |
| 4a   | `groot_grafieke.py`, `groot_stap4a.py`, `test_groot_grafieke.py`             | Bottelnekgrafieke (maksimum vloei en minimum snit)                                                                                                       |
| 4b   | `groot_tydgrafieke.py`, `groot_stap4b.py`, `test_groot_tydgrafieke.py`       | Tydgrafieke vir sortering, roetes en Kruskal (lees `groot_resultate.json`)                                                                               |
| 4c   | `groot_grafieke_stap3.py`, `groot_stap4c.py`, `test_groot_grafieke_stap3.py` | Lambda-, parallel- en spanboomgrafieke (lees `groot_resultate_stap3.json`)                                                                               |

Die vertoning gebruik slegs pakkette wat reeds in `requirements.txt` staan
(Matplotlib, pytest, ens.). Niks nuuts hoef geïnstalleer te word nie.

## Die egte data aan die vertoning koppel

Die generator (`genereer_toetsdata`) is 'n plekhouer. Om die egte ~2000
datapunte te gebruik, gee twee CSV-lêers met 'n opskrifreël.

`nodusse.csv`:

| Kolom            | Betekenis                                                |
| ---------------- | -------------------------------------------------------- |
| `node_id`        | Unieke ID                                                |
| `etiket`         | Naam                                                     |
| `vloer`          | Vloervlak as heelgetal (0 is die grondvloer)             |
| `pos_x`, `pos_y` | Koördinate in meter                                      |
| `tipe_kode`      | Bv. `DEPARTEMENT`, `INGANG`, `TRAPHUIS`, `HUISBAK_GROEP` |
| `is_nooduitgang` | `1`/`0` (ook `true`/`false` of `ja`/`nee`)               |

`rande.csv`:

| Kolom                 | Betekenis                                              |
| --------------------- | ------------------------------------------------------ |
| `van_node`, `na_node` | Die twee nodusse                                       |
| `rand_tipe`           | `GANG`, `TRAPPE`, `HUISBAK`, `LUGBRUG` of `TONNEL`     |
| `afstand_m`           | Afstand in meter                                       |
| `gewig_s`             | Reistyd in sekondes (basis plus wagtyd saam)           |
| `kapasiteit`          | Persone per sekonde; leeg gebruik `VERSTEK_KAPASITEIT` |
| `bidirectional`       | `1`/`0`; leeg is `1`                                   |

Het die egte data ander kolomname, pas slegs `laai_csv()` in `groot_data.py`
aan. Foute in die CSV gee 'n boodskap met die reëlnommer.

Let op dat `groot_parallel.py` nodusse na `Skema.sql` se `node_tipes` skryf, dus
moet elke `tipe_kode` een van `AANSLUITING`, `HUISBAK_GROEP`, `TRAPHUIS`,
`DEUR`, `INGANG`, `LUGBRUG`, `TONNEL` of `DEPARTEMENT` wees. Die parallelle
eksperiment gebruik die generator; om dit op die egte data te laat loop,
moet `bou_grawe` in `groot_stap3.py` na `laai_csv` verwys.

## Loopvolgorde

Vanuit die projekgids:

```powershell
python Groot_projek/groot_stap1.py                      # tellings, basiese tye en bottelnekke
python Groot_projek/groot_stap2.py                      # sortering, roetes en Kruskal; stoor groot_resultate.json
python Groot_projek/groot_stap3.py --werkers 1,2,4      # lambda en parallel; stoor groot_resultate_stap3.json
python Groot_projek/groot_stap4a.py --uitgids grafieke  # bottelnekgrafieke
python Groot_projek/groot_stap4b.py --uitgids grafieke  # tydgrafieke
python Groot_projek/groot_stap4c.py --uitgids grafieke  # lambda-, parallel- en spanboomgrafieke
```

Gebruik `--csv nodusse.csv rande.csv` by `groot_stap1.py`, `groot_stap2.py`,
`groot_stap4a.py` en `groot_stap4c.py` vir die egte data. Elke stap het ook
`--help`. Nuttige opsies:

| Opsie                              | Stap | Effek                                  |
| ---------------------------------- | ---- | -------------------------------------- |
| `--vinnig`                         | 2, 3 | Klein toetslopie van 'n paar sekondes  |
| `--groottes 500,2000,10000`        | 2    | Eie grootte-leer                       |
| `--net sorteer,kruskal`            | 2    | Net sommige eksperimente               |
| `--tydgrens 5`                     | 2, 3 | Stadiger voorspellings word oorgeslaan |
| `--herhalings 3`                   | 2, 3 | Minder herhalings per meting           |
| `--net lambda` of `--net parallel` | 3    | Net een helfte van fase 3              |
| `--dekking-groottes 2000`          | 3    | Net die dekking op een grootte         |
| `--spanboom-vloer 1`               | 4c   | Ander vloer vir die spanboomtekening   |

Doen 'n voorbereidingslopie van stap 2 en 3 voor die aanbieding, sodat jy
'n eerlike rugsteun het as die rekenaar in die klas stadiger is.

## Hoe om die syfers te lees

- **Tellings** (vergelykings, nodusse uitgebrei, tou-werk, vloei,
  spanboomgewig) is vir vaste data en dieselfde implementasie meer
  herhaalbaar as tye. Gelyke prioriteite of verskillende tie-breekreëls kan
  die gekose pad en besoektellings verander sonder om die optimum te verander.
- **Tye** hang van die rekenaar af. Elke tyd het 'n opwarmlopie en
  herhalings; die mediaan, minimum en maksimum word gewys.
- **`oorgeslaan`** beteken die voorspelde tyd (vorige tyd × (n / vorige n)²)
  was oor die tydgrens. Dit is 'n konserwatiewe voorspelling, nie 'n meting
  van daardie grootte nie. Die kwadratiese aanname geld nie ewe goed vir elke
  algoritme nie; die eerste meting het geen harde tydlimiet nie.
- **Versnelling** is sekwensiële mediaan gedeel deur parallelle mediaan.
  Onder 1.0x is parallel stadiger.

## Wat die eksperimente wys

| Eksperiment     | Wat jy behoort te sien                                                                                                                                                 |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sortering       | Invoegsortering groei kwadraties op ewekansige en omgekeerde invoer en is vinnig op reeds gesorteerde invoer (n−1 vergelykings); saamsmeltsortering groei soos n log n |
| Dijkstra en A\* | Dieselfde minimum tyd; A\* kan minder nodusse uitbrei; die woordeboek met `min()` doen die meeste tou-werk                                                          |
| Kruskal         | Dieselfde spanboomgewig met elke sorteermetode; met invoegsortering is byna al die tyd sortering                                                                       |
| Maksimum vloei  | Die minimum snit se kapasiteite tel op tot die vloei; in die voorbeelddata is die trappe die bottelnek                                                                 |
| Wat-as          | Breër trappe verhoog die vloei net tot gange ook beperk                                                                                                                |
| Lambda          | `lambda` en `def` se tye is gewoonlik naby; inline vermy die funksie-aanroep                                                                                                  |
| Parallel        | Die koste van prosesopstart en dataoordrag teenoor die wins van meer kerne                                                                                             |

Voorbeelduitslae hierbo is op gegenereerde data en een kern gemeet; jou
syfers sal verskil, maar die tellings en die patrone behoort dieselfde te bly.

## Beperkings

- Die gegenereerde data is 'n plekhouer. Die trappe is doelbewus as die
  bottelnek gemodelleer; dit is 'n demonstrasie, nie 'n gemete hospitaal nie.
- Randkapasiteite is demonstrasiewaardes in persone per sekonde, nie
  gekalibreerde metings nie. Geen resultaat hier vervang 'n gevalideerde
  ontruimingsplan nie.
- Parallelle spoed hang van die kerne af. Op een kern kan parallel nie wen
  nie, en die gemete versnelling is dan ruis. Die kerntal word saam met die
  resultate gestoor en op die parallelgrafiek gewys.
- Die dekkingskontrole bou per nodus die omgekeerde grafiek weer op, dus
  groei die sekwensiële tyd ongeveer met die kwadraat van die nodusgetal
  (ongeveer 0.8 s by 500 nodusse en 18 s by 2000 in die voorbeeldlopie).
  Gebruik `--tydgrens` op 'n stadige rekenaar.
- Die tou-variante en tydmetings gebruik `heapq`, `bisect` en `time` uit
  Python se standaardbiblioteek. Python se `sorted()` word slegs as
  verwysingslyn gebruik en is nie deel van die projek se handgeskrewe
  algoritmes nie.
- Kruskal se `UnionFind` (met rang en padkompressie) kom uit
  `mst_en_vloei.py` en word nie teen 'n naiewe weergawe vergelyk nie.

## Toetse

```powershell
python -m pytest -q                     # die hele stel, hoofprojek en vertoning
python -m pytest Groot_projek -q
```

Die toetse gebruik klein grafieke en tydelike lêers, en hulle verander nie die
databasis of enige projeklêer nie. Die parallelle toetse begin werklike
werkprosesse en kan dus 'n paar sekondes neem.
