"""API-toetse gebruik 'n tydelike databasis en raak nie plaaslike insidente nie."""

import pytest
from fastapi.testclient import TestClient


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


@pytest.fixture
def admin_client():
    """
    'n TestClient wat reeds as administrateur aangemeld is.

    Die autouse-fixture hier bo loop altyd eerste, dus gebruik hierdie client
    die tydelike databasis en bekende bewyse. By die einde van die toets sluit
    die with-blok die toepassing (en sy werkprosespoel) netjies af.
    """
    import main

    with TestClient(main.app) as client:
        antwoord = client.post(
            "/admin/login",
            json={"gebruikersnaam": main.ADMIN_GEBRUIKERSNAAM, "wagwoord": main.ADMIN_WAGWOORD},
        )
        assert antwoord.status_code == 200
        yield client
