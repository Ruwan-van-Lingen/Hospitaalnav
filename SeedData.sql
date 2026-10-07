-- ============================================================
-- Voorbeelddata vir 'n klein hospitaal met twee geboue.
-- Die hoofgebou het drie vloere en die bygebou het twee vloere. 'n Lugbrug
-- op vlak 1 en 'n tonnel op die grondvloer verbind die geboue.
-- ============================================================

INSERT OR IGNORE INTO geboue (gebou_id, naam, beskrywing) VALUES
    ('MAIN',  'Hoofhospitaalgebou', 'Noodgevalle, sale en operasieteaters'),
    ('SYGEBOU', 'Sygebou', 'Uitpasiënte, radiologie en administrasie');

INSERT OR IGNORE INTO vloere (vloer_id, gebou_id, level_nommer, naam) VALUES
    ('MAIN-G',  'MAIN',  0, 'Grondvloer'),
    ('MAIN-1',  'MAIN',  1, 'Vlak 1 - Sale'),
    ('MAIN-2',  'MAIN',  2, 'Vlak 2 - Intensiewe sorg / Operasieteaters'),
    ('SYGEBOU-G', 'SYGEBOU', 0, 'Grondvloer'),
    ('SYGEBOU-1', 'SYGEBOU', 1, 'Vlak 1 - Radiologie');

-- ---------------- Nodusse ----------------

-- is_nooduitgang=1 merk die nooduitgange in hierdie demonstrasiegrafiek.
-- Die voorbeeld gebruik grondvloeringange; die merk bewys nie werklike veiligheid nie.
INSERT OR IGNORE INTO nodes (node_id, vloer_id, tipe_kode, etiket, pos_x, pos_y, is_beperk, beperkte_groep, is_nooduitgang) VALUES
    -- Hoofgebou: grondvloer
    ('MAIN-G-ENT',   'MAIN-G', 'INGANG',         'Hoofingang',           0,  0, 0, NULL, 1),
    ('MAIN-G-AMB',   'MAIN-G', 'INGANG',         'Ambulansbaai',          0, 20, 0, NULL, 1),
    ('MAIN-G-J01',   'MAIN-G', 'AANSLUITING',    'Voorportaalaansluiting', 10, 0, 0, NULL, 0),
    ('MAIN-G-ELV',   'MAIN-G', 'HUISBAK_GROEP',  'Hoofhysbakgroep',       15,  5, 0, NULL, 0),
    ('MAIN-G-STA',   'MAIN-G', 'TRAPHUIS',       'Hooftraphuis',          15, 10, 0, NULL, 0),
    ('MAIN-G-ER',    'MAIN-G', 'DEPARTEMENT',    'Nooddienste',           5, 20, 0, NULL, 0),
    ('MAIN-G-TUN',   'MAIN-G', 'TONNEL',         'Tonnel na Sygebou',     10, 30, 0, NULL, 0),
    ('MAIN-G-J02',   'MAIN-G', 'AANSLUITING',    'Westelike gangaansluiting', 20, 0, 0, NULL, 0),
    ('MAIN-G-ADM',   'MAIN-G', 'DEPARTEMENT',    'Pasiënttoelatings',      25, -5, 0, NULL, 0),
    ('MAIN-G-PHA',   'MAIN-G', 'DEPARTEMENT',    'Hoofapteek',            25,  5, 0, NULL, 0),
    ('MAIN-G-BLO',   'MAIN-G', 'DEPARTEMENT',    'Bloedbank',             30, -5, 0, NULL, 0),
    ('MAIN-G-SEC',   'MAIN-G', 'DEPARTEMENT',    'Sekuriteitskantoor',    30,  5, 0, NULL, 0),

    -- Hoofgebou: vlak 1
    ('MAIN-1-ELV',   'MAIN-1', 'HUISBAK_GROEP',  'Hysbakgroep Vlak 1',    15,  5, 0, NULL, 0),
    ('MAIN-1-STA',   'MAIN-1', 'TRAPHUIS',       'Traphuis Vlak 1',       15, 10, 0, NULL, 0),
    ('MAIN-1-J01',   'MAIN-1', 'DEPARTEMENT',    'Saalgangaansluiting',   20,  5, 0, NULL, 0),
    ('MAIN-1-WARDA', 'MAIN-1', 'DEPARTEMENT',    'Saal A',               25,  0, 0, NULL, 0),
    ('MAIN-1-WARDB', 'MAIN-1', 'DEPARTEMENT',    'Saal B',               25, 10, 0, NULL, 0),
    ('MAIN-1-BRIDGE','MAIN-1', 'LUGBRUG',        'Lugbrug na Sygebou',    30, 20, 0, NULL, 0),
    ('MAIN-1-J02',   'MAIN-1', 'AANSLUITING',    'Westelike saalaansluiting', 30, 5, 0, NULL, 0),
    ('MAIN-1-WARDC', 'MAIN-1', 'DEPARTEMENT',    'Saal C',               35,  0, 0, NULL, 0),
    ('MAIN-1-PED',   'MAIN-1', 'DEPARTEMENT',    'Pediatriese saal',     35, 10, 0, NULL, 0),
    ('MAIN-1-MAT',   'MAIN-1', 'DEPARTEMENT',    'Kraamsaal',            40,  0, 0, NULL, 0),
    ('MAIN-1-FAM',   'MAIN-1', 'DEPARTEMENT',    'Familie-wagarea',      40, 10, 0, NULL, 0),

    -- Hoofgebou: vlak 2 (beperkte intensiewesorg- en operasieteatergebied)
    ('MAIN-2-ELV',   'MAIN-2', 'HUISBAK_GROEP', 'Hysbakgroep Vlak 2',     15,  5, 0, NULL, 0),
    ('MAIN-2-STA',   'MAIN-2', 'TRAPHUIS',      'Traphuis Vlak 2',        15, 10, 0, NULL, 0),
    ('MAIN-2-J01',   'MAIN-2', 'AANSLUITING',   'Intensiewesorgaansluiting', 20, 5, 1, 'SLEGS_ICU', 0),
    ('MAIN-2-ICU',   'MAIN-2', 'DEPARTEMENT',   'Intensiewe sorg',        25,  0, 1, 'SLEGS_ICU', 0),
    ('MAIN-2-OR',    'MAIN-2', 'DEPARTEMENT',   'Operasieteater',         25, 10, 1, 'SLEGS_PERSONEEL', 0),
    ('MAIN-2-REC',   'MAIN-2', 'DEPARTEMENT',   'Herstelkamer',           35, 10, 1, 'SLEGS_PERSONEEL', 0),
    ('MAIN-2-STER',  'MAIN-2', 'DEPARTEMENT',   'Steriele voorraad',      35, 15, 1, 'SLEGS_PERSONEEL', 0),
    ('MAIN-2-NICU',  'MAIN-2', 'DEPARTEMENT',   'Neonatale intensiewe sorg', 35, 0, 1, 'SLEGS_ICU', 0),
    ('MAIN-2-NUR',   'MAIN-2', 'DEPARTEMENT',   'Personeelstasie',        30, 15, 1, 'SLEGS_PERSONEEL', 0),

    -- Sygebou: grondvloer
    ('SYGEBOU-G-ENT',  'SYGEBOU-G','INGANG',         'Sygebou-ingang',        40,  0, 0, NULL, 1),
    ('SYGEBOU-G-J01',  'SYGEBOU-G','AANSLUITING',    'Sygebou-voorportaalaansluiting', 40, 10, 0, NULL, 0),
    ('SYGEBOU-G-ELV',  'SYGEBOU-G','HUISBAK_GROEP',  'Sygebou-hysbak',        40, 15, 0, NULL, 0),
    ('SYGEBOU-G-TUN',  'SYGEBOU-G','TONNEL',         'Tonnel na Hoofgebou',   10, 30, 0, NULL, 0),
    ('SYGEBOU-G-OUT',  'SYGEBOU-G','DEPARTEMENT',    'Uitpasiëntontvangs',    45, 10, 0, NULL, 0),
    ('SYGEBOU-G-LAB',  'SYGEBOU-G','DEPARTEMENT',    'Patologielaboratorium', 50,  5, 0, NULL, 0),
    ('SYGEBOU-G-CAF',  'SYGEBOU-G','DEPARTEMENT',    'Kafeteria',             50, 15, 0, NULL, 0),
    ('SYGEBOU-G-PHY',  'SYGEBOU-G','DEPARTEMENT',    'Fisioterapie',          55,  5, 0, NULL, 0),
    ('SYGEBOU-G-BIL',  'SYGEBOU-G','DEPARTEMENT',    'Rekeninge-afdeling',    55, 15, 0, NULL, 0),

    -- Sygebou: vlak 1
    ('SYGEBOU-1-ELV',  'SYGEBOU-1','HUISBAK_GROEP', 'Sygebou-hysbak Vlak 1',  40, 15, 0, NULL, 0),
    ('SYGEBOU-1-BRIDGE','SYGEBOU-1','LUGBRUG',       'Lugbrug na Hoofgebou',   30, 20, 0, NULL, 0),
    ('SYGEBOU-1-RAD',   'SYGEBOU-1','DEPARTEMENT',   'Radiologie',            45, 20, 0, NULL, 0),
    ('SYGEBOU-1-J01',   'SYGEBOU-1','AANSLUITING',   'Beeldvormingsaansluiting', 50, 20, 0, NULL, 0),
    ('SYGEBOU-1-CT',    'SYGEBOU-1','DEPARTEMENT',   'CT-skandering',         55, 15, 0, NULL, 0),
    ('SYGEBOU-1-MRI',   'SYGEBOU-1','DEPARTEMENT',   'MRI-eenheid',           55, 25, 0, NULL, 0),
    ('SYGEBOU-1-US',    'SYGEBOU-1','DEPARTEMENT',   'Ultraklank',            60, 15, 0, NULL, 0),
    ('SYGEBOU-1-XRAY',  'SYGEBOU-1','DEPARTEMENT',   'X-straaleenheid',       60, 20, 0, NULL, 0),
    ('SYGEBOU-1-NUC',   'SYGEBOU-1','DEPARTEMENT',   'Kerngeneeskunde',       60, 25, 0, NULL, 0);

-- ---------------- Rande ----------------
-- Gangrande: basis_gewig_s is ongeveer afstand gedeel deur 'n gemiddelde
-- loopsnelheid van 1,2 meter per sekonde.
-- Hysbakrande: afstand_m is 0, wag_penalty_s is die gemiddelde wagtyd en
-- vloer_verander is die absolute verskil tussen die vloervlakke.
-- Lugbrug- en tonnelrande is gewone geweegde verbindings tussen geboue.

INSERT OR IGNORE INTO rande (van_node, na_node, rand_tipe, afstand_m, basis_gewig_s, wag_penalty_s, vloer_verander, bidirectional) VALUES
    -- Hoofgebou: grondvloergange
    ('MAIN-G-ENT', 'MAIN-G-J01', 'GANG', 10, 8, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-ELV', 'GANG', 6,  5, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-STA', 'GANG', 10, 8, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-ER',  'GANG', 22, 18, 0, 0, 1),
    ('MAIN-G-AMB', 'MAIN-G-ER',  'GANG', 6,  5, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-TUN', 'GANG', 32, 27, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-J02', 'GANG', 10, 8, 0, 0, 1),
    ('MAIN-G-J02', 'MAIN-G-ADM', 'GANG', 7, 6, 0, 0, 1),
    ('MAIN-G-J02', 'MAIN-G-PHA', 'GANG', 7, 6, 0, 0, 1),
    ('MAIN-G-ADM', 'MAIN-G-BLO', 'GANG', 5, 4, 0, 0, 1),
    ('MAIN-G-PHA', 'MAIN-G-SEC', 'GANG', 5, 4, 0, 0, 1),
    ('MAIN-G-BLO', 'MAIN-G-SEC', 'GANG', 10, 8, 0, 0, 1),

    -- Hoofgebou: vertikale beweging tussen die grondvloer, vlak 1 en vlak 2
    ('MAIN-G-ELV', 'MAIN-1-ELV', 'HUISBAK', 0, 8,  25, 1, 1),
    ('MAIN-1-ELV', 'MAIN-2-ELV', 'HUISBAK', 0, 8,  25, 1, 1),
    ('MAIN-G-ELV', 'MAIN-2-ELV', 'HUISBAK', 0, 14, 25, 2, 1),
    ('MAIN-G-STA', 'MAIN-1-STA', 'TRAPPE',  0, 15, 0,  1, 1),
    ('MAIN-1-STA', 'MAIN-2-STA', 'TRAPPE',  0, 15, 0,  1, 1),

    -- Hoofgebou: gange op vlak 1
    ('MAIN-1-ELV', 'MAIN-1-J01',    'GANG',    6,  5,  0, 0, 1),
    ('MAIN-1-STA', 'MAIN-1-J01',    'GANG',    6,  5,  0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-WARDA',  'GANG',  6, 5, 0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-WARDB',  'GANG',  6, 5, 0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-BRIDGE', 'GANG', 16, 13, 0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-J02',    'GANG', 10, 8, 0, 0, 1),
    ('MAIN-1-J02', 'MAIN-1-WARDC',  'GANG', 7, 6, 0, 0, 1),
    ('MAIN-1-J02', 'MAIN-1-PED',    'GANG', 7, 6, 0, 0, 1),
    ('MAIN-1-WARDC','MAIN-1-MAT',   'GANG', 5, 4, 0, 0, 1),
    ('MAIN-1-PED',  'MAIN-1-FAM',   'GANG', 5, 4, 0, 0, 1),
    ('MAIN-1-MAT',  'MAIN-1-FAM',   'GANG', 10, 8, 0, 0, 1),

    -- Hoofgebou: beperkte gange op vlak 2
    ('MAIN-2-ELV', 'MAIN-2-J01', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-STA', 'MAIN-2-J01', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-J01', 'MAIN-2-ICU', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-J01', 'MAIN-2-OR',  'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-OR',  'MAIN-2-REC', 'GANG', 10, 8, 0, 0, 1),
    ('MAIN-2-REC', 'MAIN-2-STER','GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-ICU', 'MAIN-2-NICU','GANG', 10, 8, 0, 0, 1),
    ('MAIN-2-OR',  'MAIN-2-NUR', 'GANG', 7, 6, 0, 0, 1),
    ('MAIN-2-NUR', 'MAIN-2-STER','GANG', 5, 4, 0, 0, 1),

    -- Sygebou: grondvloergange
    ('SYGEBOU-G-ENT', 'SYGEBOU-G-J01', 'GANG', 10, 8, 0, 0, 1),
    ('SYGEBOU-G-J01', 'SYGEBOU-G-ELV', 'GANG', 6,  5, 0, 0, 1),
    ('SYGEBOU-G-J01', 'SYGEBOU-G-OUT', 'GANG', 6,  5, 0, 0, 1),
    ('SYGEBOU-G-J01', 'SYGEBOU-G-TUN', 'GANG', 30, 25, 0, 0, 1),
    ('SYGEBOU-G-J01', 'SYGEBOU-G-LAB', 'GANG', 11, 9, 0, 0, 1),
    ('SYGEBOU-G-J01', 'SYGEBOU-G-CAF', 'GANG', 11, 9, 0, 0, 1),
    ('SYGEBOU-G-LAB', 'SYGEBOU-G-PHY', 'GANG', 5, 4, 0, 0, 1),
    ('SYGEBOU-G-CAF', 'SYGEBOU-G-BIL', 'GANG', 5, 4, 0, 0, 1),
    ('SYGEBOU-G-PHY', 'SYGEBOU-G-BIL', 'GANG', 10, 8, 0, 0, 1),

    -- Sygebou: vertikale beweging
    ('SYGEBOU-G-ELV', 'SYGEBOU-1-ELV', 'HUISBAK', 0, 8, 25, 1, 1),

    -- Sygebou: vlak 1
    ('SYGEBOU-1-ELV', 'SYGEBOU-1-BRIDGE', 'GANG', 10, 8, 0, 0, 1),
    ('SYGEBOU-1-ELV', 'SYGEBOU-1-RAD',    'GANG', 6,  5, 0, 0, 1),
    ('SYGEBOU-1-RAD', 'SYGEBOU-1-J01',    'GANG', 6, 5, 0, 0, 1),
    ('SYGEBOU-1-J01', 'SYGEBOU-1-CT',     'GANG', 7, 6, 0, 0, 1),
    ('SYGEBOU-1-J01', 'SYGEBOU-1-MRI',    'GANG', 7, 6, 0, 0, 1),
    ('SYGEBOU-1-CT',  'SYGEBOU-1-US',     'GANG', 5, 4, 0, 0, 1),
    ('SYGEBOU-1-J01', 'SYGEBOU-1-XRAY',   'GANG', 10, 8, 0, 0, 1),
    ('SYGEBOU-1-MRI', 'SYGEBOU-1-NUC',    'GANG', 5, 4, 0, 0, 1),

    -- Verbindings tussen geboue
    ('MAIN-1-BRIDGE', 'SYGEBOU-1-BRIDGE', 'LUGBRUG',    25, 21, 0, 0, 1),
    ('MAIN-G-TUN',     'SYGEBOU-G-TUN',   'TONNEL',    18, 15, 0, 0, 1);

INSERT OR IGNORE INTO noodkodes (kode_id, naam) VALUES
    ('ONDERHOUD', 'Onderhoud'),
    ('SKOONMAAK', 'Skoonmaak');

-- Outomatiese noodkodes: geen noduskeuse deur die administrateur word vereis
-- nie; die gedrag word deur outomaties_modus in main.py afgedwing.
INSERT OR IGNORE INTO noodkodes (kode_id, naam, outomaties_modus) VALUES
    ('ROOI', 'Kode Rooi — Brand (ontruim almal)', 'ONTRUIM_ALMAL'),
    ('PINK', 'Kode Pink — Ontvoering (algehele grendel)', 'SLUIT_ALLES');

-- Voorafkeuses vir gewone insidenttipes word op die administrasieblad gemerk.
-- Die administrateur kan dit voor aktivering aanpas.
INSERT OR IGNORE INTO noodkode_vooraf_nodes (kode_id, node_id) VALUES
    ('ONDERHOUD', 'MAIN-G-ELV'),
    ('ONDERHOUD', 'MAIN-1-ELV'),
    ('ONDERHOUD', 'MAIN-2-ELV'),
    ('ONDERHOUD', 'SYGEBOU-G-ELV'),
    ('ONDERHOUD', 'SYGEBOU-1-ELV'),
    ('SKOONMAAK', 'MAIN-1-WARDA'),
    ('SKOONMAAK', 'MAIN-1-WARDB'),
    ('SKOONMAAK', 'MAIN-2-OR');
