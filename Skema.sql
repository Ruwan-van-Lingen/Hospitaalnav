-- ============================================================
-- Hospitaal Wayfinding Sisteem - Databasis Skema
-- Topologiese grafiek model: nodes besluit punte, rante = weighted paths
-- ============================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------
-- Geboue (n hospitaal kampus mag baie bevat wat gelink word deur
-- lug brue / tonnels)
-- ----------------------------------------------------------
CREATE TABLE geboue (
    gebou_id        TEXT PRIMARY KEY,      -- vb. 'MAIN', 'ANNEX'
    naam            TEXT NOT NULL,
    beskrywing      TEXT
);

-- ----------------------------------------------------------
-- Vloere (behoort aan n gebou)
-- ----------------------------------------------------------
CREATE TABLE vloere (
    vloer_id         TEXT PRIMARY KEY,      -- vb. 'MAIN-1', 'ANNEX-G'
    gebou_id         TEXT NOT NULL REFERENCES geboue(gebou_id),
    level_nommer     INTEGER NOT NULL,      -- 0 = grond, negatief = basement
    naam             TEXT NOT NULL          -- vb. 'Grond Vloer', 'Level 3'
);

-- ----------------------------------------------------------
-- Node tipes - beheer hoe n node gedra in padfind 
-- (hysbak/trappe nodes dra n vloer verander penalty,
--  lug brue/tonnels nodes link geboue, ens.)
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
    ('TRAPHUIS',            'Trappe toegang punt'),
    ('DEUR',                'Deur tussen die gang en die kamer/saal'),
    ('INGANG',              'Gebou ingang (publiek/ambulans/personeel)'),
    ('LUGBRUG',             'Lug brug konneksie punt tussen geboue'),
    ('TONNEL',              'Ondergrondse tonnel konneksie punt'),
    ('DEPARTEMENT',         'Departement / kamer bestemming node');

-- ----------------------------------------------------------
-- Nodes - besluit punte in die topologiese grafiek 
-- ----------------------------------------------------------
CREATE TABLE nodes (
    node_id         TEXT PRIMARY KEY,      -- vb. 'MAIN-1-J07'
    vloer_id        TEXT NOT NULL REFERENCES vloere(vloer_id),
    tipe_kode       TEXT NOT NULL REFERENCES node_tipes(tipe_kode),
    etiket          TEXT NOT NULL,         -- Naam ('Radiologie Ontvangs')
    pos_x           REAL NOT NULL,         -- lokaale koordinaate op vloer plan (meters)
    pos_y           REAL NOT NULL,
    is_beperk       INTEGER NOT NULL DEFAULT 0,  -- 1 = in n verbode wing (soos OR ens.)
    beperkte_groep  TEXT                  -- vb. 'SLEGS_PERSONEEL','ICU_ONLY', NULL if open
);

CREATE INDEX idx_nodes_vloer ON nodes(vloer_id);

-- ----------------------------------------------------------
-- Randte - weighted konneksies tussen nodes 
-- Gestoor as directe pare so asimetriese gewigte is moontelik
-- (vb. hysbak wag tyd is net van toepassing op opklim nie alighting)
-- ----------------------------------------------------------
CREATE TABLE rande (
    rand_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    van_node        TEXT NOT NULL REFERENCES nodes(node_id),
    na_node         TEXT NOT NULL REFERENCES nodes(node_id),
    rand_tipe       TEXT NOT NULL DEFAULT 'GANG',  -- 'GANG','HUISBAK','TRAPPE',
                                                   -- 'LUGBRUG','TONNEL'
    afstand_m      REAL NOT NULL,          -- fiesiese afstand (0 vir hysbak hop)
    basis_gewig_s   REAL NOT NULL,          -- travel time in sekondes vir normale walking pace
    wag_penalty_s   REAL NOT NULL DEFAULT 0, -- vb. gemiddelde hysbak wag tyd
    vloer_verander  INTEGER NOT NULL DEFAULT 0, -- hoeveelheid vloere oorgesteek (vir heuristic)
    bidirectional   INTEGER NOT NULL DEFAULT 1,
    UNIQUE(van_node, na_node)
);

CREATE INDEX idx_rande_van ON rande(van_node);
CREATE INDEX idx_rande_na ON rande(na_node);

-- ----------------------------------------------------------
-- Gebruiker tipes - dinamiese exclusion van beperkte nodes 
-- (publiek, personeel, pasient-transport, noodgeval, ens.)
-- ----------------------------------------------------------
CREATE TABLE gebruiker_tipes (
    gebruiker_tipe       TEXT PRIMARY KEY,      -- 'PUBLIEK','PERSONEEL','PASIENT_VERVOER','NOODGEVAL'
    beskrywing           TEXT
);

INSERT INTO gebruiker_tipes (gebruiker_tipe, beskrywing) VALUES
    ('PUBLIEK',            'Algemene besoekers / pasiente'),
    ('PERSONEEL',              'Hospitaal personeel, all saale'),
    ('PASIENT_VERVOER',    'Porters/vervoer met beperkte-saal toegang'),
    ('NOODGEVAL',          'Noodgeval reaksie, alle toegang');

-- Watter beperkte_groep waardes elke gebruiker tipe in mag gaan.
-- As n node se 'beperkte_groep' geen ooreenstemmende ry het vir n bepaaled gebruiker_tipe nie, is daai node uitgesluit van die grafiek vir hulle
CREATE TABLE toegang_toestemmings (
    gebruiker_tipe        TEXT NOT NULL REFERENCES gebruiker_tipes(gebruiker_tipe),
    beperkte_groep        TEXT NOT NULL,
    PRIMARY KEY (gebruiker_tipe, beperkte_groep)
);

INSERT INTO toegang_toestemmings (gebruiker_tipe, beperkte_groep) VALUES
    ('PERSONEEL', 'SLEGS_PERSONEEL'),
    ('PERSONEEL', 'ICU_ONLY'),
    ('PASIENT_VERVOER', 'SLEGS_PERSONEEL'),
    ('NOODGEVAL', 'SLEGS_PERSONEEL'),
    ('NOODGEVAL', 'ICU_ONLY');
