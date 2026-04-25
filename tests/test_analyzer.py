import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services import analyzer


@pytest.fixture
def mock_anthropic_client():
    with patch("backend.services.analyzer._anthropic") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def sample_listing_data():
    return {
        "title": "2015 BMW X5 xDrive35i",
        "year": 2015,
        "make": "BMW",
        "model": "X5",
        "mileage": 85000,
        "damage_primary": "Front End",
        "damage_secondary": "Minor Dent/Scratches",
        "location": "NJ - Glassboro",
        "current_bid_usd": 8500.0,
        "buy_now_usd": 12000.0,
        "vin": "5UXKR0C58F0P12345",
    }


@pytest.fixture
def sample_photos():
    return [
        "https://cs.copart.com/v1/AUTH_svc.pdoc/lpp/0124/5uxkr0c58f0p12345_ful.jpg",
        "https://cs.copart.com/v1/AUTH_svc.pdoc/lpp/0124/5uxkr0c58f0p12345_2_ful.jpg",
    ]


@pytest.fixture
def mock_ai_response():
    return {
        "damage_score": 4,
        "primary_damage_areas": ["Front bumper", "Hood", "Right fender"],
        "structural_damage": False,
        "airbags_deployed": False,
        "frame_damage_risk": False,
        "flood_water_damage_risk": False,
        "interior_damage": False,
        "repair_estimate_usd": {"low": 2500, "high": 3500},
        "repair_notes": "Front end cosmetic damage. Bumper, hood, and fender need replacement. No structural issues visible.",
        "red_flags": [],
        "worth_buying": True,
        "confidence": "high",
    }


@pytest.mark.asyncio
async def test_analyze_listing_success(
    mock_anthropic_client, sample_listing_data, sample_photos, mock_ai_response
):
    # Mock HTTP client for image fetching
    with patch("backend.services.analyzer.httpx.AsyncClient") as mock_http:
        mock_response = AsyncMock()
        mock_response.content = b"fake_image_data"
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_http.return_value.__aenter__.return_value = mock_client_instance

        # Mock Anthropic API response
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(type="text", text=json.dumps(mock_ai_response))
        ]
        mock_message.usage = MagicMock(
            input_tokens=1500,
            output_tokens=300,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=1200,
        )
        mock_anthropic_client.messages.create.return_value = mock_message

        result = await analyzer.analyze_listing(sample_listing_data, sample_photos)

        assert result["damage_score"] == 4
        assert result["repair_estimate_usd"]["low"] == 2500
        assert result["repair_estimate_usd"]["high"] == 3500
        assert result["worth_buying"] is True
        assert result["confidence"] == "high"
        assert "_usage" in result
        assert result["_usage"]["input_tokens"] == 1500


@pytest.mark.asyncio
async def test_analyze_listing_with_max_photos(
    mock_anthropic_client, sample_listing_data, mock_ai_response
):
    many_photos = [f"https://example.com/photo_{i}.jpg" for i in range(20)]

    with patch("backend.services.analyzer.httpx.AsyncClient") as mock_http:
        mock_response = AsyncMock()
        mock_response.content = b"fake_image_data"
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_http.return_value.__aenter__.return_value = mock_client_instance

        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(type="text", text=json.dumps(mock_ai_response))
        ]
        mock_message.usage = MagicMock(
            input_tokens=1500, output_tokens=300, cache_read_input_tokens=0,
            cache_creation_input_tokens=1200
        )
        mock_anthropic_client.messages.create.return_value = mock_message

        result = await analyzer.analyze_listing(
            sample_listing_data, many_photos, max_photos=6
        )

        # Should only fetch 6 photos
        assert mock_client_instance.get.call_count == 6
        assert result["damage_score"] == 4


@pytest.mark.asyncio
async def test_analyze_listing_json_parse_failure(
    mock_anthropic_client, sample_listing_data, sample_photos
):
    with patch("backend.services.analyzer.httpx.AsyncClient") as mock_http:
        mock_response = AsyncMock()
        mock_response.content = b"fake_image_data"
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_http.return_value.__aenter__.return_value = mock_client_instance

        # Return invalid JSON
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(type="text", text="This is not valid JSON")
        ]
        mock_message.usage = MagicMock(
            input_tokens=1500, output_tokens=50, cache_read_input_tokens=0,
            cache_creation_input_tokens=0
        )
        mock_anthropic_client.messages.create.return_value = mock_message

        result = await analyzer.analyze_listing(sample_listing_data, sample_photos)

        # Should return fallback response
        assert result["damage_score"] == 5
        assert result["worth_buying"] is False
        assert result["confidence"] == "low"
        assert "parsing failure" in result["repair_notes"]


def test_build_listing_context(sample_listing_data):
    context = analyzer._build_listing_context(sample_listing_data)

    assert "title: 2015 BMW X5 xDrive35i" in context
    assert "year: 2015" in context
    assert "make: BMW" in context
    assert "mileage: 85000" in context
    assert "damage_primary: Front End" in context
