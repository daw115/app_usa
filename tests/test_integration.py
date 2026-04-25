import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import Session, select

from backend.db import engine
from backend.models import Inquiry, InquiryStatus, Listing, Report, Settings
from backend.services.scrapers.base import ScrapedListing
from backend.tasks import generate_report, run_search_pipeline


@pytest.fixture
def mock_scrapers():
    """Mock all scrapers to return fake listings with photos"""
    fake_listings = [
        ScrapedListing(
            source="copart",
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
            photos=[
                "https://cs.copart.com/v1/AUTH_svc.pdoc/lpp/0124/photo1_ful.jpg",
                "https://cs.copart.com/v1/AUTH_svc.pdoc/lpp/0124/photo2_ful.jpg",
            ],
        ),
        ScrapedListing(
            source="iaai",
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
            photos=[
                "https://vis.iaai.com/photo1.jpg",
                "https://vis.iaai.com/photo2.jpg",
            ],
        ),
    ]

    with patch("backend.tasks.amerpol") as mock_amerpol, \
         patch("backend.tasks.copart") as mock_copart, \
         patch("backend.tasks.iaai") as mock_iaai, \
         patch("backend.tasks.fetch_nbp_usd_rate") as mock_nbp:

        mock_amerpol.search = AsyncMock(return_value=[])
        mock_amerpol.__name__ = "amerpol"
        mock_copart.search = AsyncMock(return_value=[fake_listings[0]])
        mock_copart.__name__ = "copart"
        mock_iaai.search = AsyncMock(return_value=[fake_listings[1]])
        mock_iaai.__name__ = "iaai"
        mock_nbp.return_value = 4.0

        yield {
            "amerpol": mock_amerpol,
            "copart": mock_copart,
            "iaai": mock_iaai,
        }


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic API for analyzer and synthesizer"""
    with patch("backend.services.analyzer._anthropic") as mock_analyzer, \
         patch("backend.services.synthesizer._anthropic") as mock_synthesizer:

        # Mock analyzer response
        analyzer_response = {
            "damage_score": 4,
            "primary_damage_areas": ["Front bumper", "Hood"],
            "structural_damage": False,
            "airbags_deployed": False,
            "frame_damage_risk": False,
            "flood_water_damage_risk": False,
            "interior_damage": False,
            "repair_estimate_usd": {"low": 2500, "high": 3500},
            "repair_notes": "Front end cosmetic damage.",
            "red_flags": [],
            "worth_buying": True,
            "confidence": "high",
        }

        analyzer_message = MagicMock()
        analyzer_message.content = [
            MagicMock(type="text", text=json.dumps(analyzer_response))
        ]
        analyzer_message.usage = MagicMock(
            input_tokens=1500, output_tokens=300,
            cache_read_input_tokens=0, cache_creation_input_tokens=1200
        )

        analyzer_client = MagicMock()
        analyzer_client.messages.create.return_value = analyzer_message
        mock_analyzer.return_value = analyzer_client

        # Mock synthesizer response
        synthesizer_html = """
        <p>Dzień dobry,</p>
        <p>Znalazłem kilka interesujących opcji BMW X5.</p>
        <table><tr><td>2015 BMW X5</td><td>72000 PLN</td></tr></table>
        """

        synthesizer_message = MagicMock()
        synthesizer_message.content = [
            MagicMock(type="text", text=synthesizer_html)
        ]

        synthesizer_client = MagicMock()
        synthesizer_client.messages.create.return_value = synthesizer_message
        mock_synthesizer.return_value = synthesizer_client

        yield {
            "analyzer": mock_analyzer,
            "synthesizer": mock_synthesizer,
        }


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for image fetching"""
    with patch("backend.services.analyzer.httpx.AsyncClient") as mock_http:
        mock_response = AsyncMock()
        mock_response.content = b"fake_image_data"
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_http.return_value.__aenter__.return_value = mock_client_instance

        yield mock_http


@pytest.fixture
def mock_telegram():
    """Mock Telegram notifications"""
    with patch("backend.services.telegram_bot.notify_new_inquiry") as mock_new, \
         patch("backend.services.telegram_bot.notify_report_ready") as mock_ready, \
         patch("backend.services.telegram_bot.notify_error") as mock_error:

        mock_new.return_value = AsyncMock()
        mock_ready.return_value = AsyncMock()
        mock_error.return_value = AsyncMock()

        yield {
            "new_inquiry": mock_new,
            "report_ready": mock_ready,
            "error": mock_error,
        }


@pytest.mark.asyncio
async def test_full_pipeline_integration(
    mock_scrapers, mock_anthropic, mock_http_client, mock_telegram
):
    """Test complete pipeline: inquiry → search → analyze → rank → report"""

    # Create test inquiry
    with Session(engine) as s:
        inquiry = Inquiry(
            client_name="Jan Kowalski",
            client_email="jan@example.com",
            make="BMW",
            model="X5",
            year_from=2013,
            year_to=2017,
            budget_pln=80000,
            status=InquiryStatus.new,
        )
        s.add(inquiry)
        s.commit()
        s.refresh(inquiry)
        inquiry_id = inquiry.id

    # Run search pipeline
    await run_search_pipeline(inquiry_id)

    # Verify inquiry status updated
    with Session(engine) as s:
        inquiry = s.get(Inquiry, inquiry_id)
        assert inquiry.status == InquiryStatus.ready

    # Verify listings created
    with Session(engine) as s:
        listings = s.exec(
            select(Listing).where(Listing.inquiry_id == inquiry_id)
        ).all()
        assert len(listings) == 2

        # Check first listing (Copart)
        copart_listing = next(l for l in listings if l.source.value == "copart")
        assert copart_listing.vin == "5UXKR0C58F0P12345"
        assert copart_listing.year == 2015
        assert copart_listing.make == "BMW"
        assert copart_listing.model == "X5"
        assert len(json.loads(copart_listing.photos_json)) == 2

        # Check AI analysis applied
        assert copart_listing.ai_damage_score == 4
        assert copart_listing.ai_repair_estimate_usd_low == 2500.0
        assert copart_listing.ai_repair_estimate_usd_high == 3500.0
        assert "Front end cosmetic damage" in copart_listing.ai_notes

        # Check pricing calculated
        assert copart_listing.total_cost_pln is not None
        assert copart_listing.total_cost_pln > 0

        # Check ranking applied
        assert copart_listing.recommended_rank is not None
        assert copart_listing.recommended_rank in [1, 2]

    # Generate report
    report_id = await generate_report(inquiry_id)

    # Verify report created
    with Session(engine) as s:
        report = s.get(Report, report_id)
        assert report is not None
        assert report.inquiry_id == inquiry_id
        assert "BMW X5" in report.subject
        assert "Dzień dobry" in report.html_body
        assert len(json.loads(report.selected_listing_ids)) > 0

    # Cleanup
    with Session(engine) as s:
        s.delete(s.get(Report, report_id))
        for listing in s.exec(
            select(Listing).where(Listing.inquiry_id == inquiry_id)
        ).all():
            s.delete(listing)
        s.delete(s.get(Inquiry, inquiry_id))
        s.commit()


@pytest.mark.asyncio
async def test_pipeline_handles_scraper_failures(mock_anthropic, mock_http_client):
    """Test pipeline continues when some scrapers fail"""

    with patch("backend.tasks.amerpol") as mock_amerpol, \
         patch("backend.tasks.copart") as mock_copart, \
         patch("backend.tasks.iaai") as mock_iaai, \
         patch("backend.tasks.fetch_nbp_usd_rate") as mock_nbp:

        # Amerpol fails
        mock_amerpol.search = AsyncMock(side_effect=Exception("Scraper timeout"))
        mock_amerpol.__name__ = "amerpol"

        # Copart succeeds
        mock_copart.search = AsyncMock(return_value=[
            ScrapedListing(
                source="copart",
                source_url="https://www.copart.com/lot/12345",
                title="2015 BMW X5",
                photos=["https://example.com/photo.jpg"],
            )
        ])
        mock_copart.__name__ = "copart"

        # IAAI succeeds
        mock_iaai.search = AsyncMock(return_value=[])
        mock_iaai.__name__ = "iaai"

        mock_nbp.return_value = 4.0

        with Session(engine) as s:
            inquiry = Inquiry(
                client_name="Test User",
                client_email="test@example.com",
                make="BMW",
                model="X5",
                status=InquiryStatus.new,
            )
            s.add(inquiry)
            s.commit()
            s.refresh(inquiry)
            inquiry_id = inquiry.id

        await run_search_pipeline(inquiry_id)

        # Pipeline should complete despite one scraper failing
        with Session(engine) as s:
            inquiry = s.get(Inquiry, inquiry_id)
            assert inquiry.status == InquiryStatus.ready

            listings = s.exec(
                select(Listing).where(Listing.inquiry_id == inquiry_id)
            ).all()
            assert len(listings) >= 1  # At least Copart succeeded

        # Cleanup
        with Session(engine) as s:
            for listing in s.exec(
                select(Listing).where(Listing.inquiry_id == inquiry_id)
            ).all():
                s.delete(listing)
            s.delete(s.get(Inquiry, inquiry_id))
            s.commit()
