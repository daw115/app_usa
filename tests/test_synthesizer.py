from unittest.mock import MagicMock, patch

import pytest

from backend.models import DamageTolerance, Inquiry, Listing, Source
from backend.services import synthesizer


@pytest.fixture
def sample_inquiry():
    return Inquiry(
        id=1,
        client_name="Jan Kowalski",
        client_email="jan@example.com",
        make="BMW",
        model="X5",
        year_from=2013,
        year_to=2017,
        budget_pln=80000,
        mileage_max=150000,
        body_type="SUV",
        fuel="Benzyna",
        transmission="Automatyczna",
        damage_tolerance=DamageTolerance.light,
        extra_notes="Preferuję czarny kolor, skórzana tapicerka",
    )


@pytest.fixture
def sample_listings():
    return [
        Listing(
            id=1,
            inquiry_id=1,
            source=Source.copart,
            source_url="https://www.copart.com/lot/12345",
            vin="5UXKR0C58F0P12345",
            title="2015 BMW X5 xDrive35i",
            year=2015,
            make="BMW",
            model="X5",
            mileage=85000,
            damage_primary="Front End",
            damage_secondary="Minor Dent/Scratches",
            location="NJ - Glassboro",
            current_bid_usd=8500.0,
            ai_damage_score=4,
            ai_repair_estimate_usd_low=2500.0,
            ai_repair_estimate_usd_high=3500.0,
            ai_notes="Front end cosmetic damage. Bumper, hood, fender need replacement.",
            total_cost_pln=72000.0,
            recommended_rank=1,
            excluded=False,
        ),
        Listing(
            id=2,
            inquiry_id=1,
            source=Source.iaai,
            source_url="https://www.iaai.com/vehicle/67890",
            vin="WBAKF8C55CE123456",
            title="2014 BMW X5 xDrive35d",
            year=2014,
            make="BMW",
            model="X5",
            mileage=95000,
            damage_primary="Rear",
            location="TX - Houston",
            current_bid_usd=7200.0,
            ai_damage_score=3,
            ai_repair_estimate_usd_low=1800.0,
            ai_repair_estimate_usd_high=2400.0,
            ai_notes="Minor rear damage, tailgate and bumper.",
            total_cost_pln=65000.0,
            recommended_rank=2,
            excluded=False,
        ),
    ]


@pytest.fixture
def mock_anthropic_client():
    with patch("backend.services.synthesizer._anthropic") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


def test_synthesize_report_success(
    mock_anthropic_client, sample_inquiry, sample_listings
):
    mock_html = """
    <p>Dzień dobry Panie Janie,</p>
    <p>Przeanalizowałem dostępne aukcje i znalazłem kilka interesujących opcji BMW X5.</p>
    <table style="border-collapse: collapse; width: 100%;">
        <tr><th>Rok/Model</th><th>Przebieg</th><th>Szkoda</th><th>Koszt (PLN)</th><th>Link</th></tr>
        <tr><td>2015 BMW X5</td><td>85000 km</td><td>4/10</td><td><strong>72 000 PLN</strong></td><td><a href="https://www.copart.com/lot/12345">Zobacz</a></td></tr>
    </table>
    <p>Polecam pierwszy pojazd - najlepszy stosunek ceny do stanu.</p>
    """

    mock_message = MagicMock()
    mock_message.content = [MagicMock(type="text", text=mock_html)]
    mock_anthropic_client.messages.create.return_value = mock_message

    subject, html = synthesizer.synthesize_report(sample_inquiry, sample_listings)

    assert "2015 BMW X5" in subject
    assert "Oferta aut z USA" in subject
    assert "Dzień dobry" in html
    assert "72 000 PLN" in html
    mock_anthropic_client.messages.create.assert_called_once()
    call_kwargs = mock_anthropic_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-opus-4-7"
    assert call_kwargs["max_tokens"] == 3000


def test_synthesize_report_only_includes_ranked_listings(
    mock_anthropic_client, sample_inquiry, sample_listings
):
    sample_listings.append(
        Listing(
            id=3,
            inquiry_id=1,
            source=Source.copart,
            source_url="https://www.copart.com/lot/99999",
            title="2016 BMW X5",
            year=2016,
            make="BMW",
            model="X5",
            excluded=True,
            recommended_rank=None,
        )
    )

    mock_message = MagicMock()
    mock_message.content = [MagicMock(type="text", text="<p>Test</p>")]
    mock_anthropic_client.messages.create.return_value = mock_message

    synthesizer.synthesize_report(sample_inquiry, sample_listings)

    call_kwargs = mock_anthropic_client.messages.create.call_args[1]
    user_content = call_kwargs["messages"][0]["content"]
    assert "lot/99999" not in user_content
    assert "lot/12345" in user_content


def test_compact_listing():
    listing = Listing(
        id=1,
        inquiry_id=1,
        source=Source.copart,
        source_url="https://www.copart.com/lot/12345",
        vin="5UXKR0C58F0P12345",
        title="2015 BMW X5",
        year=2015,
        make="BMW",
        model="X5",
        mileage=85000,
        damage_primary="Front End",
        current_bid_usd=8500.0,
        ai_damage_score=4,
        ai_repair_estimate_usd_low=2500.0,
        ai_repair_estimate_usd_high=3500.0,
        ai_notes="Test notes",
        total_cost_pln=72000.0,
        recommended_rank=1,
    )

    result = synthesizer._compact_listing(listing)

    assert result["id"] == 1
    assert result["source"] == "copart"
    assert result["year"] == 2015
    assert result["ai_damage_score"] == 4
    assert result["ai_repair_estimate_usd"]["low"] == 2500.0
    assert result["ai_repair_estimate_usd"]["high"] == 3500.0
    assert result["total_cost_pln"] == 72000.0
