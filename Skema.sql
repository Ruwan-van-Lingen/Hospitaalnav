-- ============================================================
-- Hospitaalnavigasiestelsel – databasisskema
-- Topologiese grafiekmodel: nodusse is keusepunte en rande is geweegde paaie.
-- ============================================================
PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------
-- Geboue ('n hospitaalkampus kan verskeie geboue bevat wat deur
-- lugbrûe of tonnels verbind word)
-- ----------------------------------------------------------
CREATE TABLE
    geboue (
        gebou_id TEXT PRIMARY KEY, -- vb. 'MAIN', 'SYGEBOU'
        naam TEXT NOT NULL,
        beskrywing TEXT
    );

-- ----------------------------------------------------------
-- Vloere (elke vloer behoort aan 'n gebou)
-- ----------------------------------------------------------
CREATE TABLE
    vloere (
        vloer_id TEXT PRIMARY KEY, -- vb. 'MAIN-1', 'SYGEBOU-G'
        gebou_id TEXT NOT NULL REFERENCES geboue (gebou_id),
        level_nommer INTEGER NOT NULL, -- 0 is die grondvloer; negatiewe waardes is keldervloere.
        naam TEXT NOT NULL -- Byvoorbeeld 'Grondvloer' of 'Vlak 3'.
    );

-- ----------------------------------------------------------
-- Nodustipes bepaal hoe 'n nodus tydens roetebepaling optree.
-- Hysbak- en trapnodusse verbind vloere; lugbrug- en tonnelnodusse
-- verbind afsonderlike geboue.
-- ----------------------------------------------------------
CREATE TABLE
    node_tipes (
        tipe_kode TEXT PRIMARY KEY, -- 'AANSLUITING','HUISBAK_GROEP','TRAPHUIS',
        -- 'DEUR','INGANG','LUGBRUG','TONNEL',
        -- 'DEPARTEMENT'
        beskrywing TEXT
    );

INSERT INTO
    node_tipes (tipe_kode, beskrywing)
VALUES
    ('AANSLUITING', 'Gang aansluiting / keuse punt'),
    ('HUISBAK_GROEP', 'Huisbak op n gegewe vloer'),
    ('TRAPHUIS', 'Trappe toegang punt'),
    ('DEUR', 'Deur tussen die gang en die kamer/saal'),
    (
        'INGANG',
        'Gebou ingang (publiek/ambulans/personeel)'
    ),
    (
        'LUGBRUG',
        'Lug brug konneksie punt tussen geboue'
    ),
    ('TONNEL', 'Ondergrondse tonnel konneksie punt'),
    (
        'DEPARTEMENT',
        'Departement / kamer bestemming node'
    );

-- ----------------------------------------------------------
-- Nodusse is keusepunte en bestemmings in die topologiese grafiek.
-- ----------------------------------------------------------
CREATE TABLE
    nodes (
        node_id TEXT PRIMARY KEY, -- Byvoorbeeld 'MAIN-1-J07'.
        vloer_id TEXT NOT NULL REFERENCES vloere (vloer_id),
        tipe_kode TEXT NOT NULL REFERENCES node_tipes (tipe_kode),
        etiket TEXT NOT NULL, -- Mensleesbare naam, byvoorbeeld 'Radiologie-ontvangs'.
        pos_x REAL NOT NULL, -- Plaaslike x-koördinaat op die vloerplan, in meter.
        pos_y REAL NOT NULL,
        is_beperk INTEGER NOT NULL DEFAULT 0, -- 1 dui 'n beperkte gebied aan.
        beperkte_groep TEXT -- Toegangsgroep, of NULL wanneer die nodus oop is.
    );

CREATE INDEX idx_nodes_vloer ON nodes (vloer_id);

-- ----------------------------------------------------------
-- Rande is geweegde verbindings tussen nodusse.
-- Gerigte pare maak verskillende kostes in teenoorgestelde rigtings moontlik.
-- ----------------------------------------------------------
CREATE TABLE
    rande (
        rand_id INTEGER PRIMARY KEY AUTOINCREMENT,
        van_node TEXT NOT NULL REFERENCES nodes (node_id),
        na_node TEXT NOT NULL REFERENCES nodes (node_id),
        rand_tipe TEXT NOT NULL DEFAULT 'GANG', -- 'GANG','HUISBAK','TRAPPE',
        -- 'LUGBRUG','TONNEL'
        afstand_m REAL NOT NULL, -- Fisiese afstand; 0 vir 'n hysbakbeweging.
        basis_gewig_s REAL NOT NULL, -- Basiese reistyd in sekondes teen 'n normale looptempo.
        wag_penalty_s REAL NOT NULL DEFAULT 0, -- Bykomende wagtyd, byvoorbeeld vir 'n hysbak.
        vloer_verander INTEGER NOT NULL DEFAULT 0, -- Aantal vloere wat oorgesteek word.
        bidirectional INTEGER NOT NULL DEFAULT 1,
        UNIQUE (van_node, na_node)
    );

CREATE INDEX idx_rande_van ON rande (van_node);

CREATE INDEX idx_rande_na ON rande (na_node);

-- ----------------------------------------------------------
-- Gebruikerstipes bepaal dinamies watter beperkte nodusse uitgesluit word,
-- byvoorbeeld vir die publiek, personeel, pasiëntvervoer en noodgevalle.
-- ----------------------------------------------------------
CREATE TABLE
    gebruiker_tipes (
        gebruiker_tipe TEXT PRIMARY KEY, -- 'PUBLIEK','PERSONEEL','PASIENT_VERVOER','NOODGEVAL'
        beskrywing TEXT
    );

INSERT INTO
    gebruiker_tipes (gebruiker_tipe, beskrywing)
VALUES
    ('PUBLIEK', 'Algemene besoekers / pasiente'),
    ('PERSONEEL', 'Hospitaal personeel, all saale'),
    (
        'PASIENT_VERVOER',
        'Porters/vervoer met beperkte-saal toegang'
    ),
    ('NOODGEVAL', 'Noodgeval reaksie, alle toegang');

-- Koppel elke gebruikerstipe aan die beperkte groepe wat hulle mag betree.
-- 'n Nodus word vir die gebruiker uitgesluit wanneer geen ooreenstemmende
-- toestemming vir die nodus se beperkte_groep bestaan nie.
CREATE TABLE
    toegang_toestemmings (
        gebruiker_tipe TEXT NOT NULL REFERENCES gebruiker_tipes (gebruiker_tipe),
        beperkte_groep TEXT NOT NULL,
        PRIMARY KEY (gebruiker_tipe, beperkte_groep)
    );

INSERT INTO
    toegang_toestemmings (gebruiker_tipe, beperkte_groep)
VALUES
    ('PERSONEEL', 'SLEGS_PERSONEEL'),
    ('PERSONEEL', 'ICU_ONLY'),
    ('PASIENT_VERVOER', 'SLEGS_PERSONEEL'),
    ('NOODGEVAL', 'SLEGS_PERSONEEL'),
    ('NOODGEVAL', 'ICU_ONLY');

CREATE TABLE
    noodkodes (
        kode_id TEXT PRIMARY KEY, -- Byvoorbeeld 'VUUR', 'MEDIES'
        naam TEXT NOT NULL
    );

CREATE TABLE
    aktiewe_insident (
        insident_id INTEGER PRIMARY KEY CHECK (insident_id = 1),
        kode_id TEXT NOT NULL REFERENCES noodkodes (kode_id),
        beskrywing TEXT,
        geaktiveer_op TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

CREATE TABLE
    insident_nodes (
        insident_id INTEGER NOT NULL REFERENCES aktiewe_insident (insident_id) ON DELETE CASCADE,
        node_id TEXT NOT NULL REFERENCES nodes (node_id),
        PRIMARY KEY (insident_id, node_id)
    );