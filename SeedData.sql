-- ============================================================
-- Voorbeelddata: 'n klein hospitaal met twee geboue.
-- Die hoofgebou het drie vloere en die bygebou het twee vloere.
-- Hulle word met 'n lugbrug op vlak 1 en 'n tonnel op die grondvloer verbind.
-- ============================================================

INSERT INTO geboue (gebou_id, naam, beskrywing) VALUES
    ('MAIN',  'Main Hospitaal Gebou', 'Noodgeval, saale, or'),
    ('ANNEX', 'Annex Gebou', 'Uitpasiente, radiologie, admin');

INSERT INTO vloere (vloer_id, gebou_id, level_nommer, naam) VALUES
    ('MAIN-G',  'MAIN',  0, 'Grond Vloer'),
    ('MAIN-1',  'MAIN',  1, 'Level 1 - Saale'),
    ('MAIN-2',  'MAIN',  2, 'Level 2 - ICU / OR'),
    ('ANNEX-G', 'ANNEX', 0, 'Grond Vloer'),
    ('ANNEX-1', 'ANNEX', 1, 'Level 1 - Radiology');

-- ---------------- Nodusse ----------------

INSERT INTO nodes (node_id, vloer_id, tipe_kode, etiket, pos_x, pos_y, is_beperk, beperkte_groep) VALUES
    -- Hoofgebou: grondvloer
    ('MAIN-G-ENT',   'MAIN-G', 'INGANG',         'Hoof Publiek Ingang',   0,  0, 0, NULL),
    ('MAIN-G-AMB',   'MAIN-G', 'INGANG',         'Ambulaans Bay',          0, 20, 0, NULL),
    ('MAIN-G-J01',   'MAIN-G', 'AANSLUITING',    'Lobby Aansluiting',        10,  0, 0, NULL),
    ('MAIN-G-ELV',   'MAIN-G', 'HUISBAK_GROEP',  'Hoof Huisbak Groep',    15,  5, 0, NULL),
    ('MAIN-G-STA',   'MAIN-G', 'TRAPHUIS',         'Hoof Traphuis',        15, 10, 0, NULL),
    ('MAIN-G-ER',    'MAIN-G', 'DEPARTEMENT',    'Nooddienste',             5, 20, 0, NULL),
    ('MAIN-G-TUN',   'MAIN-G', 'TONNEL',         'Tonnel na Annex',       10, 30, 0, NULL),

    -- Hoofgebou: vlak 1
    ('MAIN-1-ELV',   'MAIN-1', 'HUISBAK_GROEP',  'Huisbak Groep L1',      15,  5, 0, NULL),
    ('MAIN-1-STA',   'MAIN-1', 'TRAPHUIS',       'Traphuis L1',          15, 10, 0, NULL),
    ('MAIN-1-J01',   'MAIN-1', 'DEPARTEMENT',    'Saal Gang Jct',     20,  5, 0, NULL),
    ('MAIN-1-WARDA', 'MAIN-1', 'DEPARTEMENT',    'Saal A',                25,  0, 0, NULL),
    ('MAIN-1-WARDB', 'MAIN-1', 'DEPARTEMENT',     'Saal B',                25, 10, 0, NULL),
    ('MAIN-1-BRIDGE','MAIN-1', 'LUGBRUG',        'Lug Brug na Annex',   30, 20, 0, NULL),

    -- Hoofgebou: vlak 2 (beperk – ICU en chirurgie)
    ('MAIN-2-ELV',   'MAIN-2', 'HUISBAK_GROEP', 'Huisbak Groep L2',      15,  5, 0, NULL),
    ('MAIN-2-STA',   'MAIN-2', 'TRAPHUIS',      'Traphuis L2',          15, 10, 0, NULL),
    ('MAIN-2-J01',   'MAIN-2', 'AANSLUITING',   'ICU Gang Jct',      20,  5, 1, 'ICU_ONLY'),
    ('MAIN-2-ICU',   'MAIN-2', 'DEPARTEMENT',   'ICU',                   25,  0, 1, 'ICU_ONLY'),
    ('MAIN-2-OR',    'MAIN-2', 'DEPARTEMENT',   'Operasie Teater',    25, 10, 1, 'STAFF_ONLY'),

    -- Bygebou: grondvloer
    ('ANNEX-G-ENT',  'ANNEX-G','INGANG',       'Annex Ingang',        40,  0, 0, NULL),
    ('ANNEX-G-J01',  'ANNEX-G','AANSLUITING',   'Annex Lobby Jct',       40, 10, 0, NULL),
    ('ANNEX-G-ELV',  'ANNEX-G','HUISBAK_GROEP', 'Annex Huisbak',        40, 15, 0, NULL),
    ('ANNEX-G-TUN',  'ANNEX-G','TONNEL',        'Tonnel na Main',        10, 30, 0, NULL),
    ('ANNEX-G-OUT',  'ANNEX-G','DEPARTEMENT',   'Uitpasient Ontvangs', 45, 10, 0, NULL),

    -- Bygebou: vlak 1
    ('ANNEX-1-ELV',  'ANNEX-1','HUISBAK_GROEP', 'Annex Huisbak L1',     40, 15, 0, NULL),
    ('ANNEX-1-BRIDGE','ANNEX-1','LUGBRUG',      'Lug Brug na Main',    30, 20, 0, NULL),
    ('ANNEX-1-RAD',   'ANNEX-1','DEPARTEMENT',  'Radiologie',             45, 20, 0, NULL);

-- ---------------- Rande ----------------
-- Gangrande: basis_gewig_s is ongeveer afstand gedeel deur gemiddelde loopsnelheid (1,2 m/s).
-- Hysbakrande: afstand_m = 0, wag_penalty_s = gemiddelde wagtyd en vloer_verander = |verskil|.
-- Lugbrug- en tonnelrande: gewone geweegde gangrande tussen geboue.

INSERT INTO rande (van_node, na_node, rand_tipe, afstand_m, basis_gewig_s, wag_penalty_s, vloer_verander, bidirectional) VALUES
    -- Hoofgebou: grondvloergange
    ('MAIN-G-ENT', 'MAIN-G-J01', 'GANG', 10, 8, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-ELV', 'GANG', 6,  5, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-STA', 'GANG', 10, 8, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-ER',  'GANG', 22, 18, 0, 0, 1),
    ('MAIN-G-AMB', 'MAIN-G-ER',  'GANG', 6,  5, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-TUN', 'GANG', 32, 27, 0, 0, 1),

    -- Hoofgebou: vertikale beweging (grondvloer <-> vlak 1 <-> vlak 2)
    ('MAIN-G-ELV', 'MAIN-1-ELV', 'HUISBAK', 0, 8,  25, 1, 1),
    ('MAIN-1-ELV', 'MAIN-2-ELV', 'HUISBAK', 0, 8,  25, 1, 1),
    ('MAIN-G-ELV', 'MAIN-2-ELV', 'HUISBAK', 0, 14, 25, 2, 1),
    ('MAIN-G-STA', 'MAIN-1-STA', 'TRAPPE',   0, 15, 0,  1, 1),
    ('MAIN-1-STA', 'MAIN-2-STA', 'TRAPPE',   0, 15, 0,  1, 1),

    -- Hoofgebou: gange op vlak 1
    ('MAIN-1-ELV', 'MAIN-1-J01', 'GANG', 6,  5,  0, 0, 1),
    ('MAIN-1-STA', 'MAIN-1-J01', 'GANG', 6,  5,  0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-WARDA', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-WARDB', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-BRIDGE', 'GANG', 16, 13, 0, 0, 1),

    -- Hoofgebou: gange op vlak 2 (beperk)
    ('MAIN-2-ELV', 'MAIN-2-J01', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-STA', 'MAIN-2-J01', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-J01', 'MAIN-2-ICU', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-J01', 'MAIN-2-OR',  'GANG', 6, 5, 0, 0, 1),

    -- Bygebou: grondvloergange
    ('ANNEX-G-ENT', 'ANNEX-G-J01', 'GANG', 10, 8, 0, 0, 1),
    ('ANNEX-G-J01', 'ANNEX-G-ELV', 'GANG', 6,  5, 0, 0, 1),
    ('ANNEX-G-J01', 'ANNEX-G-OUT', 'GANG', 6,  5, 0, 0, 1),
    ('ANNEX-G-J01', 'ANNEX-G-TUN', 'GANG', 30, 25, 0, 0, 1),

    -- Bygebou: vertikale beweging
    ('ANNEX-G-ELV', 'ANNEX-1-ELV', 'HUISBAK', 0, 8, 25, 1, 1),

    -- Bygebou: vlak 1
    ('ANNEX-1-ELV', 'ANNEX-1-BRIDGE', 'GANG', 10, 8, 0, 0, 1),
    ('ANNEX-1-ELV', 'ANNEX-1-RAD',    'GANG', 6,  5, 0, 0, 1),

    -- Verbindings tussen geboue
    ('MAIN-1-BRIDGE', 'ANNEX-1-BRIDGE', 'LUGBRUG', 25, 21, 0, 0, 1),
    ('MAIN-G-TUN',     'ANNEX-G-TUN',    'TONNEL',    18, 15, 0, 0, 1);
