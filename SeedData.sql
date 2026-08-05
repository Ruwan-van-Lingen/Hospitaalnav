-- ============================================================
-- Sample data: n klein twee gebou hospitaal
-- MAIN gebou (3 vloere) + ANNEX geboue (2 vloere),
-- geheg deur n lug brug op level 1 en n tonnel op die grond vloer
-- ============================================================

INSERT INTO geboue (gebou_id, naam, beskrywing) VALUES
    ('MAIN',  'Main Hospitaal Gebou', 'Noodgeval, Saale, or'),
    ('ANNEX', 'Annex Gebou', 'Uitpasiente, Radiologie, Admin');

INSERT INTO vloere (vloer_id, gebou_id, level_nommer, naam) VALUES
    ('MAIN-G',  'MAIN',  0, 'Grond Vloer'),
    ('MAIN-1',  'MAIN',  1, 'Level 1 - Saale'),
    ('MAIN-2',  'MAIN',  2, 'Level 2 - ICU / OR'),
    ('ANNEX-G', 'ANNEX', 0, 'Grond Vloer'),
    ('ANNEX-1', 'ANNEX', 1, 'Level 1 - Radiology');

-- ---------------- Nodes ----------------

INSERT INTO nodes (node_id, vloer_id, tipe_kode, etiket, pos_x, pos_y, is_beperk, beperkte_groep) VALUES
    -- MAIN Grond vloer
    ('MAIN-G-ENT',   'MAIN-G', 'INGANG',         'Hoof Publiek Ingang',   0,  0, 0, NULL),
    ('MAIN-G-AMB',   'MAIN-G', 'INGANG',         'Ambulaans Baai',        0, 20, 0, NULL),
    ('MAIN-G-J01',   'MAIN-G', 'AANSLUITING',    'Lobby Aansluiting',     10,  0, 0, NULL),
    ('MAIN-G-ELV',   'MAIN-G', 'HUISBAK_GROEP',  'Hoof Huisbak Groep',    15,  5, 0, NULL),
    ('MAIN-G-STA',   'MAIN-G', 'TRAPHUIS',       'Hoof Traphuis',         15, 10, 0, NULL),
    ('MAIN-G-ER',    'MAIN-G', 'DEPARTEMENT',    'Nooddienste',           5, 20, 0, NULL),
    ('MAIN-G-TUN',   'MAIN-G', 'TONNEL',         'Tonnel na Annex',       10, 30, 0, NULL),

    -- MAIN Level 1
    ('MAIN-1-ELV',   'MAIN-1', 'HUISBAK_GROEP',  'Huisbak Groep L1',     15,  5, 0, NULL),
    ('MAIN-1-STA',   'MAIN-1', 'TRAPHUIS',       'Traphuis L1',          15, 10, 0, NULL),
    ('MAIN-1-J01',   'MAIN-1', 'DEPARTEMENT',    'Saal Gang Jct',        20,  5, 0, NULL),
    ('MAIN-1-WARDA', 'MAIN-1', 'DEPARTEMENT',    'Saal A',               25,  0, 0, NULL),
    ('MAIN-1-WARDB', 'MAIN-1', 'DEPARTEMENT',    'Saal B',               25, 10, 0, NULL),
    ('MAIN-1-BRIDGE','MAIN-1', 'LUGBRUG',        'Lug Brug na Annex',    30, 20, 0, NULL),

    -- MAIN Level 2 (beperkte - ICU/Surergie)
    ('MAIN-2-ELV',   'MAIN-2', 'HUISBAK_GROEP', 'Huisbak Groep L2',      15,  5, 0, NULL),
    ('MAIN-2-STA',   'MAIN-2', 'TRAPHUIS',      'Traphuis L2',           15, 10, 0, NULL),
    ('MAIN-2-J01',   'MAIN-2', 'AANSLUITING',   'ICU Gang Jct',          20,  5, 1, 'ICU_ONLY'),
    ('MAIN-2-ICU',   'MAIN-2', 'DEPARTEMENT',   'ICU',                   25,  0, 1, 'ICU_ONLY'),
    ('MAIN-2-OR',    'MAIN-2', 'DEPARTEMENT',   'OR',                    25, 10, 1, 'STAFF_ONLY'),

    -- ANNEX Grond vloer
    ('ANNEX-G-ENT',  'ANNEX-G','INGANG',         'Annex Ingang',              40,  0, 0, NULL),
    ('ANNEX-G-J01',  'ANNEX-G','AANSLUITING',    'Annex Lobby Jct',           40, 10, 0, NULL),
    ('ANNEX-G-ELV',  'ANNEX-G','HUISBAK_GROEP',  'Annex Huisbak',             40, 15, 0, NULL),
    ('ANNEX-G-TUN',  'ANNEX-G','TONNEL',         'Tonnel na Main',            10, 30, 0, NULL),
    ('ANNEX-G-OUT',  'ANNEX-G','DEPARTEMENT',    'Uitpasient Ontvangs',       45, 10, 0, NULL),

    -- ANNEX Level 1
    ('ANNEX-1-ELV',  'ANNEX-1','HUISBAK_GROEP', 'Annex Huisbak L1',           40, 15, 0, NULL),
    ('ANNEX-1-BRIDGE','ANNEX-1','LUGBRUG',      'Lug Brug na Main',           30, 20, 0, NULL),
    ('ANNEX-1-RAD',   'ANNEX-1','DEPARTEMENT',  'Radiologie',                 45, 20, 0, NULL);

-- ---------------- Rande ----------------
-- Gang rande: basis_gewig_s ~ afstand / avg loop spoed (1.2 m/s)
-- Huisbak rande: afstand_m = 0, wag_penalty_s = avg wag, vloer_verander = |delta|
-- Lug Brug / tonnel rande: standaard weighted gang rande tussen geboue

INSERT INTO rande (van_node, na_node, rand_tipe, afstand_m, basis_gewig_s, wag_penalty_s, vloer_verander, bidirectional) VALUES
    -- MAIN Grond vloer gange 
    ('MAIN-G-ENT', 'MAIN-G-J01', 'GANG', 10, 8, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-ELV', 'GANG', 6,  5, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-STA', 'GANG', 10, 8, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-ER',  'GANG', 22, 18, 0, 0, 1),
    ('MAIN-G-AMB', 'MAIN-G-ER',  'GANG', 6,  5, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-TUN', 'GANG', 32, 27, 0, 0, 1),

    -- MAIN vertical circulation (Grond <-> L1 <-> L2)
    ('MAIN-G-ELV', 'MAIN-1-ELV', 'HUISBAK', 0, 8,  25, 1, 1),
    ('MAIN-1-ELV', 'MAIN-2-ELV', 'HUISBAK', 0, 8,  25, 1, 1),
    ('MAIN-G-ELV', 'MAIN-2-ELV', 'HUISBAK', 0, 14, 25, 2, 1),
    ('MAIN-G-STA', 'MAIN-1-STA', 'TRAPPE',  0, 15, 0,  1, 1),
    ('MAIN-1-STA', 'MAIN-2-STA', 'TRAPPE',  0, 15, 0,  1, 1),

    -- MAIN Level 1 gange
    ('MAIN-1-ELV', 'MAIN-1-J01',    'GANG',    6,  5,  0, 0, 1),
    ('MAIN-1-STA', 'MAIN-1-J01',    'GANG',    6,  5,  0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-WARDA',  'GANG',  6, 5, 0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-WARDB',  'GANG',  6, 5, 0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-BRIDGE', 'GANG', 16, 13, 0, 0, 1),

    -- MAIN Level 2 gange (beperk)
    ('MAIN-2-ELV', 'MAIN-2-J01', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-STA', 'MAIN-2-J01', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-J01', 'MAIN-2-ICU', 'GANG', 6, 5, 0, 0, 1),
    ('MAIN-2-J01', 'MAIN-2-OR',  'GANG', 6, 5, 0, 0, 1),

    -- ANNEX Grond vloer gange
    ('ANNEX-G-ENT', 'ANNEX-G-J01', 'GANG', 10, 8, 0, 0, 1),
    ('ANNEX-G-J01', 'ANNEX-G-ELV', 'GANG', 6,  5, 0, 0, 1),
    ('ANNEX-G-J01', 'ANNEX-G-OUT', 'GANG', 6,  5, 0, 0, 1),
    ('ANNEX-G-J01', 'ANNEX-G-TUN', 'GANG', 30, 25, 0, 0, 1),

    -- ANNEX vertikale circulation
    ('ANNEX-G-ELV', 'ANNEX-1-ELV', 'HUISBAK', 0, 8, 25, 1, 1),

    -- ANNEX Level 1
    ('ANNEX-1-ELV', 'ANNEX-1-BRIDGE', 'GANG', 10, 8, 0, 0, 1),
    ('ANNEX-1-ELV', 'ANNEX-1-RAD',    'GANG', 6,  5, 0, 0, 1),

    -- Gebou-tot-gebou conneksies
    ('MAIN-1-BRIDGE', 'ANNEX-1-BRIDGE', 'LUGBRUG',    25, 21, 0, 0, 1),
    ('MAIN-G-TUN',     'ANNEX-G-TUN',    'TONNEL',    18, 15, 0, 0, 1);
