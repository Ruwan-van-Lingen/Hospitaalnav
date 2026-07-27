-- ============================================================
-- Hospital Wayfinding System - Database Schema
-- Topological graph model: nodes = decision points, edges = weighted paths
-- ============================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------
-- Buildings (a hospital campus may have several, linked by
-- sky bridges / tunnels)
-- ----------------------------------------------------------
CREATE TABLE buildings (
    building_id     TEXT PRIMARY KEY,      -- e.g. 'MAIN', 'ANNEX'
    name            TEXT NOT NULL,
    description     TEXT
);

-- ----------------------------------------------------------
-- Floors (belong to a building)
-- ----------------------------------------------------------
CREATE TABLE floors (
    floor_id        TEXT PRIMARY KEY,      -- e.g. 'MAIN-1', 'ANNEX-G'
    building_id     TEXT NOT NULL REFERENCES buildings(building_id),
    level_number    INTEGER NOT NULL,      -- 0 = ground, negative = basement
    name            TEXT NOT NULL          -- e.g. 'Ground Floor', 'Level 3'
);

-- ----------------------------------------------------------
-- Node types - controls how a node behaves in routing
-- (elevator/stairs nodes carry a floor-change penalty,
--  sky-bridge/tunnel nodes link buildings, etc.)
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
-- Nodes - decision points in the topological graph
-- ----------------------------------------------------------
CREATE TABLE nodes (
    node_id         TEXT PRIMARY KEY,      -- e.g. 'MAIN-1-J07'
    floor_id        TEXT NOT NULL REFERENCES floors(floor_id),
    type_code       TEXT NOT NULL REFERENCES node_types(type_code),
    label           TEXT NOT NULL,         -- human-readable ('Radiology Reception')
    pos_x           REAL NOT NULL,         -- local coordinate on floor plan (metres)
    pos_y           REAL NOT NULL,
    is_restricted   INTEGER NOT NULL DEFAULT 0,  -- 1 = in a restricted wing
    restricted_group TEXT                  -- e.g. 'STAFF_ONLY','ICU_ONLY', NULL if open
);

CREATE INDEX idx_nodes_floor ON nodes(floor_id);

-- ----------------------------------------------------------
-- Edges - weighted connections between nodes
-- Stored as directed pairs so asymmetric weights are possible
-- (e.g. elevator wait time only applies boarding, not alighting)
-- ----------------------------------------------------------
CREATE TABLE edges (
    edge_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    from_node       TEXT NOT NULL REFERENCES nodes(node_id),
    to_node         TEXT NOT NULL REFERENCES nodes(node_id),
    edge_type       TEXT NOT NULL DEFAULT 'CORRIDOR',  -- 'CORRIDOR','ELEVATOR','STAIRS',
                                                         -- 'SKYBRIDGE','TUNNEL'
    distance_m      REAL NOT NULL,          -- physical distance (0 for elevator hops)
    base_weight_s   REAL NOT NULL,          -- travel time in seconds at normal walking pace
    wait_penalty_s  REAL NOT NULL DEFAULT 0, -- e.g. average elevator wait time
    floor_change    INTEGER NOT NULL DEFAULT 0, -- number of floors crossed (for heuristic)
    bidirectional   INTEGER NOT NULL DEFAULT 1,
    UNIQUE(from_node, to_node)
);

CREATE INDEX idx_edges_from ON edges(from_node);
CREATE INDEX idx_edges_to ON edges(to_node);

-- ----------------------------------------------------------
-- User types - dynamic exclusion of restricted nodes
-- (public, staff, patient-transport, emergency, etc.)
-- ----------------------------------------------------------
CREATE TABLE user_types (
    user_type       TEXT PRIMARY KEY,      -- 'PUBLIC','STAFF','PATIENT_TRANSPORT','EMERGENCY'
    description     TEXT
);

INSERT INTO user_types (user_type, description) VALUES
    ('PUBLIC',            'General visitors / patients'),
    ('STAFF',              'Hospital staff, all wings'),
    ('PATIENT_TRANSPORT',  'Porters/transport with restricted-ward access'),
    ('EMERGENCY',          'Emergency response, all access');

-- Which restricted_group values each user type is allowed into.
-- If a node's restricted_group has no matching row here for a
-- given user_type, that node is excluded from the graph for them.
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
