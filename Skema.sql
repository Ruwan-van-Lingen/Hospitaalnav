-- ============================================================
-- Hospitaalnavigasiestelsel – databasisskema
-- Topologiese grafiekmodel: nodes is keusepunte en rande is geweegde paaie.
-- ============================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------
-- Geboue ('n hospitaalkampus kan verskeie geboue bevat wat deur
-- lugbrûe of tonnels verbind word)
-- ----------------------------------------------------------
CREATE TABLE geboue (
    gebou_id        TEXT PRIMARY KEY,      -- vb. 'MAIN', 'ANNEX'
    naam            TEXT NOT NULL,
    beskrywing      TEXT
);

-- ----------------------------------------------------------
-- Vloere (elke vloer behoort aan 'n gebou)
-- ----------------------------------------------------------
CREATE TABLE vloere (
    vloer_id         TEXT PRIMARY KEY,      -- vb. 'MAIN-1', 'ANNEX-G'
    gebou_id         TEXT NOT NULL REFERENCES geboue(gebou_id),
    level_nommer     INTEGER NOT NULL,      -- 0 = grondvloer, negatiewe waardes = keldervloere
    naam             TEXT NOT NULL          -- byvoorbeeld 'Grondvloer' of 'Vlak 3'
);

-- ----------------------------------------------------------
-- Nodetipes beheer hoe 'n node tydens roetebepaling optree.
-- Hysbak- en trapnodes dra 'n vloerveranderingstraf, terwyl lugbrug-
-- en tonnelnodes geboue verbind.
-- ----------------------------------------------------------
CREATE TABLE node_tipes (
    tipe_kode       TEXT PRIMARY KEY,      -- 'AANSLUITING','HUISBAK_GROEP','TRAPHUIS',
                                            -- 'DEUR','INGANG','LUGBRUG','TONNEL',
                                            -- 'DEPARTEMENT'
    beskrywing     TEXT
);

INSERT INTO node_tipes (tipe_kode, beskrywing) VALUES
    ('AANSLUITING',         'Gang aansluiting / keuse punt'),
    ('HUISBAK_GROEP',       'Huisbak op n gegewe vloer'),
    ('TRAPHUIS',             'Trappe toegang punt'),
    ('DEUR',                'Deur tussen die gang en die kamer/saal'),
    ('INGANG',              'Gebou ingang (publiek/ambulans/staff)'),
    ('LUGBRUG',             'Lug brug konneksie punt tussen geboue'),
    ('TONNEL',              'Ondergrondse tonnel konneksie punt'),
    ('DEPARTEMENT',         'Departement / kamer bestemming node');

-- ----------------------------------------------------------
-- Nodes is keusepunte in die topologiese grafiek.
-- ----------------------------------------------------------
CREATE TABLE nodes (
    node_id         TEXT PRIMARY KEY,      -- vb. 'MAIN-1-J07'
    vloer_id        TEXT NOT NULL REFERENCES vloere(vloer_id),
    tipe_kode       TEXT NOT NULL REFERENCES node_tipes(tipe_kode),
    etiket          TEXT NOT NULL,         -- Naam ('Radiologie Ontvangs')
    pos_x           REAL NOT NULL,         -- lokaale koordinaate op vloer plan (meters)
    pos_y           REAL NOT NULL,
    is_beperk       INTEGER NOT NULL DEFAULT 0,  -- 1 = in n verbode wing (soos OR ens.)
    beperkte_groep  TEXT                  -- vb. 'STAFF_ONLY','ICU_ONLY', NULL if open
);

CREATE INDEX idx_nodes_vloer ON nodes(vloer_id);

-- ----------------------------------------------------------
-- Rande is geweegde verbindings tussen nodes.
-- Hulle word as gerigte pare gestoor sodat asimmetriese gewigte moontlik is,
-- byvoorbeeld wanneer hysbakwagtyd net in een rigting van toepassing is.
-- ----------------------------------------------------------
CREATE TABLE rande (
    rand_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    van_node        TEXT NOT NULL REFERENCES nodes(node_id),
    na_node         TEXT NOT NULL REFERENCES nodes(node_id),
    rand_tipe       TEXT NOT NULL DEFAULT 'GANG',  -- 'GANG','HUISBAK','TRAPPE',
                                                   -- 'LUGBRUG','TONNEL'
    afstand_m      REAL NOT NULL,          -- fiesiese afstand (0 vir hysbak hop)
    basis_gewig_s   REAL NOT NULL,          -- reistyd in sekondes teen 'n normale looptempo
    wag_penalty_s   REAL NOT NULL DEFAULT 0, -- vb. gemiddelde hysbak wag tyd
    vloer_verander  INTEGER NOT NULL DEFAULT 0, -- aantal vloere oorgesteek (vir die heuristiek)
    bidirectional   INTEGER NOT NULL DEFAULT 1,
    UNIQUE(van_node, na_node)
);

CREATE INDEX idx_rande_van ON rande(van_node);
CREATE INDEX idx_rande_na ON rande(na_node);

-- ----------------------------------------------------------
-- Gebruikerstipes bepaal die dinamiese uitsluiting van beperkte nodes,
-- byvoorbeeld publiek, personeel, pasiëntvervoer en noodgevalle.
-- ----------------------------------------------------------
CREATE TABLE gebruiker_tipes (
    gebruiker_tipe       TEXT PRIMARY KEY,      -- 'PUBLIEK','STAFF','PASIENT_VERVOER','NOODGEVAL'
    beskrywing           TEXT
);

INSERT INTO gebruiker_tipes (gebruiker_tipe, beskrywing) VALUES
    ('PUBLIEK',            'Algemene besoekers / pasiente'),
    ('STAFF',              'Hospitaal staff, all saale'),
    ('PASIENT_VERVOER',    'Porters/vervoer met beperkte-saal toegang'),
    ('NOODGEVAL',          'Noodgeval reaksie, alle toegang');

-- Bepaal watter beperkte groepe elke gebruikerstipe mag betree.
-- As 'n node se beperkte_groep nie 'n ooreenstemmende ry vir die gebruikerstipe
-- het nie, word daardie node vir die gebruiker uit die grafiek gelaat.
CREATE TABLE toegang_toestemmings (
    gebruiker_tipe        TEXT NOT NULL REFERENCES gebruiker_tipes(gebruiker_tipe),
    beperkte_groep        TEXT NOT NULL,
    PRIMARY KEY (gebruiker_tipe, beperkte_groep)
);

INSERT INTO toegang_toestemmings (gebruiker_tipe, beperkte_groep) VALUES
    ('STAFF', 'STAFF_ONLY'),
    ('STAFF', 'ICU_ONLY'),
    ('PASIENT_VERVOER', 'STAFF_ONLY'),
    ('NOODGEVAL', 'STAFF_ONLY'),
    ('NOODGEVAL', 'ICU_ONLY');
