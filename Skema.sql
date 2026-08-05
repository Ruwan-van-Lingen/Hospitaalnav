-- ============================================================
-- Hospitaal Wayfinding Sisteem - Databasis Skema
-- Topologiese grafiek model: nodes besluit punte, rante = weighted paths
-- ============================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------
-- Geboue (n hospitaal kampus mag baie bevat wat gelink word deur
-- lug brue / tonnels)
-- ----------------------------------------------------------
CREATE TABLE buildings (
    building_id     TEXT PRIMARY KEY,      -- vb. 'MAIN', 'ANNEX'
    name            TEXT NOT NULL,
    description     TEXT
);

-- ----------------------------------------------------------
-- Vloere (behoort aan n gebou)
-- ----------------------------------------------------------
CREATE TABLE floors (
    floor_id        TEXT PRIMARY KEY,      -- vb. 'MAIN-1', 'ANNEX-G'
    building_id     TEXT NOT NULL REFERENCES buildings(building_id),
    level_number    INTEGER NOT NULL,      -- 0 = grond, negatief = basement
    name            TEXT NOT NULL          -- vb. 'Grond Vloer', 'Level 3'
);

-- ----------------------------------------------------------
-- Node tipes - beheer hoe n node gedra in padfind 
-- (hysbak/trappe nodes dra n floor verander penalty,
--  lug brue/tonnels nodes link geboue, ens.)
-- ----------------------------------------------------------
CREATE TABLE node_types (
    type_code       TEXT PRIMARY KEY,      -- 'JUNCTION','ELEVATOR_LOBBY','STAIRWELL',
                                            -- 'DOORWAY','ENTRANCE','SKYBRIDGE','TUNNEL',
                                            -- 'DEPARTMENT'
    description     TEXT
);

INSERT INTO node_types (type_code, description) VALUES
    ('JUNCTION',       'Corridor intersection / decision point'),
    ('ELEVATOR_LOBBY',  'Elevator bank on a given floor'),
    ('STAIRWELL',       'Stairwell access point'),
    ('DOORWAY',         'Doorway between corridor and room/ward'),
    ('ENTRANCE',        'Building entrance (public/ambulance/staff)'),
    ('SKYBRIDGE',       'Sky bridge connection point between buildings'),
    ('TUNNEL',          'Underground tunnel connection point'),
    ('DEPARTMENT',      'Department / room destination node');

-- ----------------------------------------------------------
-- Nodes - besluit punte in die topologiese grafiek 
-- ----------------------------------------------------------
CREATE TABLE nodes (
    node_id         TEXT PRIMARY KEY,      -- vb. 'MAIN-1-J07'
    floor_id        TEXT NOT NULL REFERENCES floors(floor_id),
    type_code       TEXT NOT NULL REFERENCES node_types(type_code),
    label           TEXT NOT NULL,         -- Naam ('Radiologie Ontvangs')
    pos_x           REAL NOT NULL,         -- lokaale koordinaate op vloer plan (meters)
    pos_y           REAL NOT NULL,
    is_restricted   INTEGER NOT NULL DEFAULT 0,  -- 1 = in n verbode wing (soos OR ens.)
    restricted_group TEXT                  -- vb. 'STAFF_ONLY','ICU_ONLY', NULL if open
);

CREATE INDEX idx_nodes_floor ON nodes(floor_id);

-- ----------------------------------------------------------
-- Randte - weighted konneksies tussen nodes 
-- Gestoor as directe pare so asimetriese gewigte is moontelik
-- (vb. hysbak wag tyd is net van toepassing op opklim nie alighting)
-- ----------------------------------------------------------
CREATE TABLE edges (
    edge_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    from_node       TEXT NOT NULL REFERENCES nodes(node_id),
    to_node         TEXT NOT NULL REFERENCES nodes(node_id),
    edge_type       TEXT NOT NULL DEFAULT 'CORRIDOR',  -- 'CORRIDOR','ELEVATOR','STAIRS',
                                                         -- 'SKYBRIDGE','TUNNEL'
    distance_m      REAL NOT NULL,          -- fiesiese afstand (0 vir hysbak hop)
    base_weight_s   REAL NOT NULL,          -- travel time in sekondes vir normale walking pace
    wait_penalty_s  REAL NOT NULL DEFAULT 0, -- vb. gemiddelde hysbak wag tyd
    floor_change    INTEGER NOT NULL DEFAULT 0, -- hoeveelheid vloere oorgesteek (vir heuristic)
    bidirectional   INTEGER NOT NULL DEFAULT 1,
    UNIQUE(from_node, to_node)
);

CREATE INDEX idx_edges_from ON edges(from_node);
CREATE INDEX idx_edges_to ON edges(to_node);

-- ----------------------------------------------------------
-- Gebruiker tipes - dinamiese exclusion van restricted nodes 
-- (publiek, staff, pasient-transport, noodgeval, ens.)
-- ----------------------------------------------------------
CREATE TABLE user_types (
    user_type       TEXT PRIMARY KEY,      -- 'PUBLIEK','STAFF','PASIENT_VERVOER','NOODGEVAL'
    description     TEXT
);

INSERT INTO user_types (user_type, description) VALUES
    ('PUBLIC',            'General visitors / patients'),
    ('STAFF',              'Hospital staff, all wings'),
    ('PATIENT_TRANSPORT',  'Porters/transport with restricted-ward access'),
    ('EMERGENCY',          'Emergency response, all access');

-- Watter restricted_groep waardes elke gebruiker tipe in mag gaan.
-- As n node se 'restricted_groep' geen matching ry het vir n bepaaled gebruiker_tipe, is daai node uitgesluit van die grafiek vir hulle
CREATE TABLE access_permissions (
    user_type        TEXT NOT NULL REFERENCES user_types(user_type),
    restricted_group TEXT NOT NULL,
    PRIMARY KEY (user_type, restricted_group)
);

INSERT INTO access_permissions (user_type, restricted_group) VALUES
    ('STAFF', 'STAFF_ONLY'),
    ('STAFF', 'ICU_ONLY'),
    ('PATIENT_TRANSPORT', 'STAFF_ONLY'),
    ('EMERGENCY', 'STAFF_ONLY'),
    ('EMERGENCY', 'ICU_ONLY');
