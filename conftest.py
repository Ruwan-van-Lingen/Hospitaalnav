"""API-toetse gebruik 'n tydelike databasis en raak nie plaaslike insidente nie."""

import pytest


@pytest.fixture(autouse=True)
def afsonder_toetsdatabasis(tmp_path, monkeypatch):
    """Gee elke toets sy eie tydelike databasis en bekende adminbewyse."""
    import main

    monkeypatch.setattr(main, "DB_PAD", tmp_path / "hospitaal.db")
    # Herbou die databasis uit Skema.sql en SeedData.sql, sodat elke toets met skoon voorbeelddata begin.
    monkeypatch.setattr(main, "AUTO_HERBOU_DB", True)
    # Bekende toetsbewyse; die toetse meld aan met admin / admin.
    monkeypatch.setattr(main, "ADMIN_GEBRUIKERSNAAM", "admin")
    monkeypatch.setattr(main, "ADMIN_WAGWOORD", "admin")
