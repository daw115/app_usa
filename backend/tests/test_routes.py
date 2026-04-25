import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

from backend.main import app
from backend.db import get_session
from backend.models import Settings, Inquiry, InquiryStatus


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Create default settings
        settings = Settings(id=1)
        session.add(settings)
        session.commit()
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_health_endpoint(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["db"] == "connected"


def test_cache_stats_endpoint(client: TestClient):
    response = client.get("/api/cache/stats")
    assert response.status_code == 200
    data = response.json()
    assert "size" in data
    assert "hits" in data
    assert "misses" in data


def test_create_inquiry(client: TestClient, session: Session):
    payload = {
        "make": "Toyota",
        "model": "Camry",
        "year_from": 2018,
        "year_to": 2020,
        "budget_pln": 50000,
        "mileage_max": 100000,
        "damage_tolerance": "minor",
        "contact_email": "test@example.com",
    }
    response = client.post("/api/inquiries", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["make"] == "Toyota"
    assert data["model"] == "Camry"
    assert data["status"] == "new"


def test_list_inquiries(client: TestClient, session: Session):
    # Create test inquiry
    inquiry = Inquiry(
        make="Honda",
        model="Civic",
        year_from=2019,
        year_to=2021,
        budget_pln=45000,
        status=InquiryStatus.new,
        contact_email="test@example.com",
    )
    session.add(inquiry)
    session.commit()

    response = client.get("/api/inquiries")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(i["make"] == "Honda" for i in data)


def test_get_inquiry(client: TestClient, session: Session):
    inquiry = Inquiry(
        make="Ford",
        model="Mustang",
        year_from=2020,
        year_to=2022,
        budget_pln=80000,
        status=InquiryStatus.new,
        contact_email="test@example.com",
    )
    session.add(inquiry)
    session.commit()
    session.refresh(inquiry)

    response = client.get(f"/api/inquiries/{inquiry.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["make"] == "Ford"
    assert data["model"] == "Mustang"


def test_update_settings(client: TestClient, session: Session):
    payload = {
        "usd_pln_rate": 4.15,
        "agent_fee_usd": 350,
        "transport_usd": 1200,
        "customs_pct": 0.10,
        "excise_pct": 0.03,
        "vat_pct": 0.23,
        "margin_pln": 5000,
        "repair_safety_pct": 0.20,
        "auto_search_enabled": True,
        "auto_usd_rate": True,
    }
    response = client.put("/api/settings", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["usd_pln_rate"] == 4.15
    assert data["agent_fee_usd"] == 350


def test_get_settings(client: TestClient):
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert "usd_pln_rate" in data
    assert "agent_fee_usd" in data
