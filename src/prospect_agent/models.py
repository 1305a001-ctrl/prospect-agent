"""Pydantic types — one per concept in the data model."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Niche = Literal["restaurant", "clinic_dental", "clinic_medical", "clinic_beauty"]


class WebsiteAnalysis(BaseModel):
    """Subset of website features the scorer uses."""
    https: bool | None = None
    mobile_score: int | None = Field(default=None, ge=0, le=100)
    has_booking: bool | None = None
    last_modified: date | None = None


class Lead(BaseModel):
    """One discovered business + features. Maps 1:1 to the `leads` table."""
    source: str = "google_maps"
    google_place_id: str | None = None
    niche: Niche
    geo_city: str | None = None
    geo_country: str = "MY"

    business_name: str
    business_address: str | None = None
    business_lat: float | None = None
    business_lng: float | None = None
    business_rating: float | None = None
    business_review_count: int | None = None
    business_phone: str | None = None
    business_website_url: str | None = None

    website: WebsiteAnalysis = Field(default_factory=WebsiteAnalysis)

    fit_score: float = Field(default=0.0, ge=0.0, le=1.0)
    score_factors: dict = Field(default_factory=dict)
    status: str = "new"
    metadata: dict = Field(default_factory=dict)
