"""Skep die JavaScript-toetse se kaart uit SQL, sonder die werklike databasis."""

import json
import sqlite3
from pathlib import Path


def kaart_toetsdata():
    gids = Path(__file__).resolve().parent
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        for naam in ("Skema.sql", "SeedData.sql"):
            conn.executescript((gids / naam).read_text(encoding="utf-8"))
        kaart = {
            "geboue": [dict(r) for r in conn.execute("SELECT gebou_id, naam FROM geboue ORDER BY gebou_id")],
            "vloere": [dict(r) for r in conn.execute("SELECT vloer_id, gebou_id, level_nommer, naam FROM vloere ORDER BY gebou_id, level_nommer")],
            "nodes": [dict(r) for r in conn.execute("SELECT node_id, vloer_id, tipe_kode, etiket, pos_x, pos_y, beperkte_groep FROM nodes ORDER BY rowid")],
            "rande": [dict(r) for r in conn.execute("SELECT van_node, na_node, rand_tipe FROM rande ORDER BY rand_id")],
        }
        kaart["bestemmings"] = [dict(r) for r in conn.execute("""
            SELECT n.node_id, n.etiket, g.naam AS gebou_naam, v.naam AS vloer_naam
            FROM nodes n JOIN vloere v USING (vloer_id) JOIN geboue g USING (gebou_id)
            WHERE n.node_id IN ('MAIN-G-ENT', 'SYGEBOU-1-RAD') ORDER BY n.rowid
        """)]
    return kaart


if __name__ == "__main__":
    print(json.dumps(kaart_toetsdata(), ensure_ascii=False))
