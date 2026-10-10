"""Maak die hoofprojek se modules beskikbaar wanneer 'n groot stap direk loop."""

import sys
from pathlib import Path

HOOF_GIDS = Path(__file__).resolve().parent.parent


def maak_hoofprojek_beskikbaar():
    pad = str(HOOF_GIDS)
    if pad not in sys.path:
        sys.path.insert(0, pad)
