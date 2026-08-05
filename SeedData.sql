-- ============================================================
-- Voorbeelddata vir 'n klein hospitaal met twee geboue.
-- Die hoofgebou het drie vloere en die bygebou het twee vloere. 'n Lugbrug
-- op vlak 1 en 'n tonnel op die grondvloer verbind die geboue.
-- ============================================================

INSERT INTO geboue (gebou_id, naam, beskrywing) VALUES
    ('MAIN',  'Main Hospitaal Gebou', 'Noodgeval, Saale, or'),
    ('SYGEBOU', 'Sygebou', 'Uitpasiente, Radiologie, Admin');

INSERT INTO vloere (vloer_id, gebou_id, level_nommer, naam) VALUES
    ('MAIN-G',  'MAIN',  0, 'Grond Vloer'),
    ('MAIN-1',  'MAIN',  1, 'Level 1 - Saale'),
    ('MAIN-2',  'MAIN',  2, 'Level 2 - ICU / OR'),
    ('SYGEBOU-G', 'SYGEBOU', 0, 'Grond Vloer'),
    ('SYGEBOU-1', 'SYGEBOU', 1, 'Level 1 - Radiology');

-- ---------------- Nodusse ----------------

INSERT INTO nodes (node_id, vloer_id, tipe_kode, etiket, pos_x, pos_y, is_beperk, beperkte_groep) VALUES
    -- Hoofgebou: grondvloer
    ('MAIN-G-ENT',   'MAIN-G', 'INGANG',         'Hoof Publiek Ingang',   0,  0, 0, NULL),
    ('MAIN-G-AMB',   'MAIN-G', 'INGANG',         'Ambulaans Baai',        0, 20, 0, NULL),
    ('MAIN-G-J01',   'MAIN-G', 'AANSLUITING',    'Lobby Aansluiting',     10,  0, 0, NULL),
    ('MAIN-G-ELV',   'MAIN-G', 'HUISBAK_GROEP',  'Hoof Huisbak Groep',    15,  5, 0, NULL),
    ('MAIN-G-STA',   'MAIN-G', 'TRAPHUIS',       'Hoof Traphuis',         15, 10, 0, NULL),
    ('MAIN-G-ER',    'MAIN-G', 'DEPARTEMENT',    'Nooddienste',           5, 20, 0, NULL),
    ('MAIN-G-TUN',   'MAIN-G', 'TONNEL',         'Tonnel na Sygebou',       10, 30, 0, NULL),

    -- Hoofgebou: vlak 1
    ('MAIN-1-ELV',   'MAIN-1', 'HUISBAK_GROEP',  'Huisbak Groep L1',     15,  5, 0, NULL),
    ('MAIN-1-STA',   'MAIN-1', 'TRAPHUIS',       'Traphuis L1',          15, 10, 0, NULL),
    ('MAIN-1-J01',   'MAIN-1', 'DEPARTEMENT',    'Saal Gang Jct',        20,  5, 0, NULL),
    ('MAIN-1-WARDA', 'MAIN-1', 'DEPARTEMENT',    'Saal A',               25,  0, 0, NULL),
    ('MAIN-1-WARDB', 'MAIN-1', 'DEPARTEMENT',    'Saal B',               25, 10, 0, NULL),
    ('MAIN-1-BRIDGE','MAIN-1', 'LUGBRUG',        'Lug Brug na Sygebou',    30, 20, 0, NULL),

    -- Hoofgebou: vlak 2 (beperkte ICU- en operasieteatergebied)
    ('MAIN-2-ELV',   'MAIN-2', 'HUISBAK_GROEP', 'Huisbak Groep L2',      15,  5, 0, NULL),
    ('MAIN-2-STA',   'MAIN-2', 'TRAPHUIS',      'Traphuis L2',           15, 10, 0, NULL),
    ('MAIN-2-J01',   'MAIN-2', 'AANSLUITING',   'ICU Gang Jct',          20,  5, 1, 'ICU_ONLY'),
    ('MAIN-2-ICU',   'MAIN-2', 'DEPARTEMENT',   'ICU',                   25,  0, 1, 'ICU_ONLY'),
    ('MAIN-2-OR',    'MAIN-2', 'DEPARTEMENT',   'OR',                    25, 10, 1, 'SLEGS_PERSONEEL'),

    -- SYGEBOU Grond vloer
    ('SYGEBOU-G-ENT',  'SYGEBOU-G','INGANG',         'Sygebou Ingang',              40,  0, 0, NULL),
    ('SYGEBOU-G-J01',  'SYGEBOU-G','AANSLUITING',    'Sygebou Lobby Jct',           40, 10, 0, NULL),
    ('SYGEBOU-G-ELV',  'SYGEBOU-G','HUISBAK_GROEP',  'Sygebou Huisbak',             40, 15, 0, NULL),
    ('SYGEBOU-G-TUN',  'SYGEBOU-G','TONNEL',         'Tonnel na Main',            10, 30, 0, NULL),
    ('SYGEBOU-G-OUT',  'SYGEBOU-G','DEPARTEMENT',    'Uitpasient Ontvangs',       45, 10, 0, NULL),

    -- SYGEBOU Level 1
    ('SYGEBOU-1-ELV',  'SYGEBOU-1','HUISBAK_GROEP', 'Sygebou Huisbak L1',           40, 15, 0, NULL),
    ('SYGEBOU-1-BRIDGE','SYGEBOU-1','LUGBRUG',      'Lug Brug na Main',           30, 20, 0, NULL),
    ('SYGEBOU-1-RAD',   'SYGEBOU-1','DEPARTEMENT',  'Radiologie',                 45, 20, 0, NULL);

-- ---------------- Rande ----------------
-- Gangrande: basis_gewig_s is ongeveer afstand gedeel deur 'n gemiddelde
-- loopsnelheid van 1,2 meter per sekonde.
-- Hysbakrande: afstand_m is 0, wag_penalty_s is die gemiddelde wagtyd en
-- vloer_verander is die absolute verskil tussen die vloervlakke.
-- Lugbrug- en tonnelrande is gewone geweegde verbindings tussen geboue.

INSERT INTO rande (van_node, na_node, rand_tipe, afstand_m, basis_gewig_s, wag_penalty_s, vloer_verander, bidirectional) VALUES
    -- Hoofgebou: grondvloergange
    ('MAIN-G-ENT', 'MAIN-G-J01', 'GANG', 10, 8, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-ELV', 'GANG', 6,  5, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-STA', 'GANG', 10, 8, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-ER',  'GANG', 22, 18, 0, 0, 1),
    ('MAIN-G-AMB', 'MAIN-G-ER',  'GANG', 6,  5, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-TUN', 'GANG', 32, 27, 0, 0, 1),

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

    -- Hoofgebou: beperkte gange op vlak 2
    ('MAIN-2-ELV', 'MAIN-2-J01', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-STA', 'MAIN-2-J01', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-J01', 'MAIN-2-ICU', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-J01', 'MAIN-2-OR',  'GANG', 6, 5, 0, 0, 1),

    -- SYGEBOU Grond vloer gange
    ('SYGEBOU-G-ENT', 'SYGEBOU-G-J01', 'GANG', 10, 8, 0, 0, 1),
    ('SYGEBOU-G-J01', 'SYGEBOU-G-ELV', 'GANG', 6,  5, 0, 0, 1),
    ('SYGEBOU-G-J01', 'SYGEBOU-G-OUT', 'GANG', 6,  5, 0, 0, 1),
    ('SYGEBOU-G-J01', 'SYGEBOU-G-TUN', 'GANG', 30, 25, 0, 0, 1),

    -- SYGEBOU vertikale circulation
    ('SYGEBOU-G-ELV', 'SYGEBOU-1-ELV', 'HUISBAK', 0, 8, 25, 1, 1),

    -- SYGEBOU Level 1
    ('SYGEBOU-1-ELV', 'SYGEBOU-1-BRIDGE', 'GANG', 10, 8, 0, 0, 1),
    ('SYGEBOU-1-ELV', 'SYGEBOU-1-RAD',    'GANG', 6,  5, 0, 0, 1),

    -- Gebou-tot-gebou conneksies
    ('MAIN-1-BRIDGE', 'SYGEBOU-1-BRIDGE', 'LUGBRUG',    25, 21, 0, 0, 1),
    ('MAIN-G-TUN',     'SYGEBOU-G-TUN',   'TONNEL',    18, 15, 0, 0, 1);
