from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class DamageTolerance(str, Enum):
    none = "none"
    light = "light"
    medium = "medium"
    heavy = "heavy"


class InquiryStatus(str, Enum):
    new = "new"
    searching = "searching"
    analyzing = "analyzing"
    ready = "ready"
    sent = "sent"
    archived = "archived"


class ReportStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    sent = "sent"


class Source(str, Enum):
    copart = "copart"
    iaai = "iaai"
    amerpol = "amerpol"
    auctiongate = "auctiongate"
    manual = "manual"


class Inquiry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    client_name: str
    client_email: str
    client_phone: str = ""
    make: str = ""
    model: str = ""
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    budget_pln: Optional[int] = None
    mileage_max: Optional[int] = None
    body_type: str = ""
    fuel: str = ""
    transmission: str = ""
    damage_tolerance: DamageTolerance = DamageTolerance.light
    extra_notes: str = ""
    status: InquiryStatus = Field(default=InquiryStatus.new, index=True)
    tracking_token: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()), index=True)


class Listing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    inquiry_id: int = Field(foreign_key="inquiry.id", index=True)
    source: Source
    source_url: str
    vin: str = ""
    title: str = ""
    year: Optional[int] = None
    make: str = ""
    model: str = ""
    mileage: Optional[int] = None
    damage_primary: str = ""
    damage_secondary: str = ""
    location: str = ""
    auction_date: str = ""
    current_bid_usd: Optional[float] = None
    buy_now_usd: Optional[float] = None
    photos_json: str = "[]"
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    ai_repair_estimate_usd_low: Optional[float] = None
    ai_repair_estimate_usd_high: Optional[float] = None
    ai_damage_score: Optional[int] = None
    ai_notes: str = ""
    ai_raw_json: str = ""
    total_cost_pln: Optional[float] = None
    recommended_rank: Optional[int] = None
    excluded: bool = False


class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    inquiry_id: int = Field(foreign_key="inquiry.id", index=True)
    html_body: str = ""
    selected_listing_ids: str = "[]"
    status: ReportStatus = ReportStatus.draft
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    gmail_draft_id: str = ""
    subject: str = ""


class Settings(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    transport_usd: float = 1500.0
    agent_fee_usd: float = 600.0
    customs_pct: float = 0.10
    excise_pct: float = 0.186
    vat_pct: float = 0.23
    margin_pln: float = 5000.0
    repair_safety_pct: float = 0.25
    usd_pln_rate: float = 4.00
    auto_usd_rate: bool = True
    auto_search_enabled: bool = False
