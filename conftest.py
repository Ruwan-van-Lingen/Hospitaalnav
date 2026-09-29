"""API-toetse gebruik 'n tydelike databasis en raak nie plaaslike insidente nie."""

import pytest


@pytest.fixture(autouse=True)
def afsonder_toetsdatabasis(tmp_path, monkeypatch):
    import main

    monkeypatch.setattr(main, "DB_PAD", tmp_path / "hospitaal.db")
    monkeypatch.setattr(main, "AUTO_HERBOU_DB", True)
    monkeypatch.setattr(main, "ADMIN_GEBRUIKERSNAAM", "admin")
    monkeypatch.setattr(main, "ADMIN_WAGWOORD", "admin")
