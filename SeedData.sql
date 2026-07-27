-- ============================================================
-- Sample data: a small two-building hospital
-- MAIN building (3 floors) + ANNEX building (2 floors),
-- linked by a sky bridge on level 1 and a tunnel at ground level.
-- ============================================================

INSERT INTO buildings (building_id, name, description) VALUES
    ('MAIN',  'Main Hospital Building', 'Emergency, wards, surgery'),
    ('ANNEX', 'Annex Building',         'Outpatients, radiology, admin');

INSERT INTO floors (floor_id, building_id, level_number, name) VALUES
    ('MAIN-G',  'MAIN',  0, 'Ground Floor'),
    ('MAIN-1',  'MAIN',  1, 'Level 1 - Wards'),
    ('MAIN-2',  'MAIN',  2, 'Level 2 - ICU / Surgery'),
    ('ANNEX-G', 'ANNEX', 0, 'Ground Floor'),
    ('ANNEX-1', 'ANNEX', 1, 'Level 1 - Radiology');

-- ---------------- Nodes ----------------

INSERT INTO nodes (node_id, floor_id, type_code, label, pos_x, pos_y, is_restricted, restricted_group) VALUES
    -- MAIN Ground floor
    ('MAIN-G-ENT',   'MAIN-G', 'ENTRANCE',       'Main Public Entrance',   0,  0, 0, NULL),
    ('MAIN-G-AMB',   'MAIN-G', 'ENTRANCE',       'Ambulance Bay',          0, 20, 0, NULL),
    ('MAIN-G-J01',   'MAIN-G', 'JUNCTION',       'Lobby Junction',        10,  0, 0, NULL),
    ('MAIN-G-ELV',   'MAIN-G', 'ELEVATOR_LOBBY', 'Main Elevator Bank',    15,  5, 0, NULL),
    ('MAIN-G-STA',   'MAIN-G', 'STAIRWELL',      'Main Stairwell',        15, 10, 0, NULL),
    ('MAIN-G-ER',    'MAIN-G', 'DEPARTMENT',     'Emergency Room',         5, 20, 0, NULL),
    ('MAIN-G-TUN',   'MAIN-G', 'TUNNEL',         'Tunnel to Annex',       10, 30, 0, NULL),

    -- MAIN Level 1
    ('MAIN-1-ELV',   'MAIN-1', 'ELEVATOR_LOBBY', 'Elevator Bank L1',      15,  5, 0, NULL),
    ('MAIN-1-STA',   'MAIN-1', 'STAIRWELL',      'Stairwell L1',          15, 10, 0, NULL),
    ('MAIN-1-J01',   'MAIN-1', 'JUNCTION',       'Ward Corridor Jct',     20,  5, 0, NULL),
    ('MAIN-1-WARDA', 'MAIN-1', 'DEPARTMENT',     'Ward A',                25,  0, 0, NULL),
    ('MAIN-1-WARDB', 'MAIN-1', 'DEPARTMENT',     'Ward B',                25, 10, 0, NULL),
    ('MAIN-1-BRIDGE','MAIN-1', 'SKYBRIDGE',      'Sky Bridge to Annex',   30, 20, 0, NULL),

    -- MAIN Level 2 (restricted - ICU/Surgery)
    ('MAIN-2-ELV',   'MAIN-2', 'ELEVATOR_LOBBY', 'Elevator Bank L2',      15,  5, 0, NULL),
    ('MAIN-2-STA',   'MAIN-2', 'STAIRWELL',      'Stairwell L2',          15, 10, 0, NULL),
    ('MAIN-2-J01',   'MAIN-2', 'JUNCTION',       'ICU Corridor Jct',      20,  5, 1, 'ICU_ONLY'),
    ('MAIN-2-ICU',   'MAIN-2', 'DEPARTMENT',     'ICU',                   25,  0, 1, 'ICU_ONLY'),
    ('MAIN-2-OR',    'MAIN-2', 'DEPARTMENT',     'Operating Theatres',    25, 10, 1, 'STAFF_ONLY'),

    -- ANNEX Ground floor
    ('ANNEX-G-ENT',  'ANNEX-G','ENTRANCE',       'Annex Entrance',        40,  0, 0, NULL),
    ('ANNEX-G-J01',  'ANNEX-G','JUNCTION',       'Annex Lobby Jct',       40, 10, 0, NULL),
    ('ANNEX-G-ELV',  'ANNEX-G','ELEVATOR_LOBBY', 'Annex Elevator',        40, 15, 0, NULL),
    ('ANNEX-G-TUN',  'ANNEX-G','TUNNEL',         'Tunnel to Main',        10, 30, 0, NULL),
    ('ANNEX-G-OUT',  'ANNEX-G','DEPARTMENT',     'Outpatients Reception', 45, 10, 0, NULL),

    -- ANNEX Level 1
    ('ANNEX-1-ELV',  'ANNEX-1','ELEVATOR_LOBBY', 'Annex Elevator L1',     40, 15, 0, NULL),
    ('ANNEX-1-BRIDGE','ANNEX-1','SKYBRIDGE',     'Sky Bridge to Main',    30, 20, 0, NULL),
    ('ANNEX-1-RAD',   'ANNEX-1','DEPARTMENT',    'Radiology',             45, 20, 0, NULL);

-- ---------------- Edges ----------------
-- Corridor edges: base_weight_s ~ distance / avg walk speed (1.2 m/s)
-- Elevator edges: distance_m = 0, wait_penalty_s = avg wait, floor_change = |delta|
-- Sky bridge / tunnel edges: standard weighted corridor edges between buildings

INSERT INTO edges (from_node, to_node, edge_type, distance_m, base_weight_s, wait_penalty_s, floor_change, bidirectional) VALUES
    -- MAIN Ground floor corridors
    ('MAIN-G-ENT', 'MAIN-G-J01', 'CORRIDOR', 10, 8, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-ELV', 'CORRIDOR', 6,  5, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-STA', 'CORRIDOR', 10, 8, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-ER',  'CORRIDOR', 22, 18, 0, 0, 1),
    ('MAIN-G-AMB', 'MAIN-G-ER',  'CORRIDOR', 6,  5, 0, 0, 1),
    ('MAIN-G-J01', 'MAIN-G-TUN', 'CORRIDOR', 32, 27, 0, 0, 1),

    -- MAIN vertical circulation (Ground <-> L1 <-> L2)
    ('MAIN-G-ELV', 'MAIN-1-ELV', 'ELEVATOR', 0, 8,  25, 1, 1),
    ('MAIN-1-ELV', 'MAIN-2-ELV', 'ELEVATOR', 0, 8,  25, 1, 1),
    ('MAIN-G-ELV', 'MAIN-2-ELV', 'ELEVATOR', 0, 14, 25, 2, 1),
    ('MAIN-G-STA', 'MAIN-1-STA', 'STAIRS',   0, 15, 0,  1, 1),
    ('MAIN-1-STA', 'MAIN-2-STA', 'STAIRS',   0, 15, 0,  1, 1),

    -- MAIN Level 1 corridors
    ('MAIN-1-ELV', 'MAIN-1-J01', 'CORRIDOR', 6,  5,  0, 0, 1),
    ('MAIN-1-STA', 'MAIN-1-J01', 'CORRIDOR', 6,  5,  0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-WARDA', 'CORRIDOR', 6, 5, 0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-WARDB', 'CORRIDOR', 6, 5, 0, 0, 1),
    ('MAIN-1-J01', 'MAIN-1-BRIDGE', 'CORRIDOR', 16, 13, 0, 0, 1),

    -- MAIN Level 2 corridors (restricted)
    ('MAIN-2-ELV', 'MAIN-2-J01', 'CORRIDOR', 6, 5, 0, 0, 1),
    ('MAIN-2-STA', 'MAIN-2-J01', 'CORRIDOR', 6, 5, 0, 0, 1),
    ('MAIN-2-J01', 'MAIN-2-ICU', 'CORRIDOR', 6, 5, 0, 0, 1),
    ('MAIN-2-J01', 'MAIN-2-OR',  'CORRIDOR', 6, 5, 0, 0, 1),

    -- ANNEX Ground floor corridors
    ('ANNEX-G-ENT', 'ANNEX-G-J01', 'CORRIDOR', 10, 8, 0, 0, 1),
    ('ANNEX-G-J01', 'ANNEX-G-ELV', 'CORRIDOR', 6,  5, 0, 0, 1),
    ('ANNEX-G-J01', 'ANNEX-G-OUT', 'CORRIDOR', 6,  5, 0, 0, 1),
    ('ANNEX-G-J01', 'ANNEX-G-TUN', 'CORRIDOR', 30, 25, 0, 0, 1),

    -- ANNEX vertical circulation
    ('ANNEX-G-ELV', 'ANNEX-1-ELV', 'ELEVATOR', 0, 8, 25, 1, 1),

    -- ANNEX Level 1
    ('ANNEX-1-ELV', 'ANNEX-1-BRIDGE', 'CORRIDOR', 10, 8, 0, 0, 1),
    ('ANNEX-1-ELV', 'ANNEX-1-RAD',    'CORRIDOR', 6,  5, 0, 0, 1),

    -- Building-to-building links
    ('MAIN-1-BRIDGE', 'ANNEX-1-BRIDGE', 'SKYBRIDGE', 25, 21, 0, 0, 1),
    ('MAIN-G-TUN',     'ANNEX-G-TUN',    'TUNNEL',    18, 15, 0, 0, 1);
