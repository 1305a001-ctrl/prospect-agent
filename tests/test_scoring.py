import pytest

from prospect_agent.models import Lead, WebsiteAnalysis
from prospect_agent.scoring import score_lead, search_query_for


def _lead(**ov) -> Lead:
    base = dict(
        niche="restaurant", geo_city="Kuala Lumpur",
        business_name="Test Cafe",
    )
    base.update(ov)
    return Lead.model_validate(base)


def test_no_website_is_strongest_signal():
    score, factors = score_lead(_lead(business_website_url=None))
    assert factors == {"no_website": 0.45}
    assert score == 0.45


def test_modern_website_scores_low():
    """Site exists, https, mobile, has booking → almost no fit."""
    lead = _lead(
        business_website_url="https://example.com",
        website=WebsiteAnalysis(https=True, mobile_score=90, has_booking=True),
    )
    score, factors = score_lead(lead)
    # Nothing failing → score=0 (modern site, generic restaurant niche)
    assert score == pytest.approx(0.0)
    assert factors == {}


def test_outdated_site_accumulates_penalties():
    lead = _lead(
        business_website_url="http://old-cafe.my",
        website=WebsiteAnalysis(https=False, mobile_score=30, has_booking=False),
    )
    score, factors = score_lead(lead)
    assert factors == {"no_https": 0.15, "poor_mobile": 0.15, "no_booking": 0.10}
    assert score == pytest.approx(0.40)


def test_rating_in_band_adds_5pct():
    lead = _lead(business_website_url=None, business_rating=4.0)
    score, factors = score_lead(lead)
    assert "rating_in_band" in factors
    assert score == pytest.approx(0.50)


def test_perfect_rating_no_bonus():
    """5.0 rating is suspicious / saturated — out of the band."""
    lead = _lead(business_website_url=None, business_rating=4.9)
    score, factors = score_lead(lead)
    assert "rating_in_band" not in factors


def test_active_business_bonus():
    lead = _lead(business_website_url=None, business_review_count=200)
    score, factors = score_lead(lead)
    assert factors.get("active_business") == 0.05


def test_clinic_aov_bonus():
    lead = _lead(niche="clinic_dental", business_website_url=None)
    score, factors = score_lead(lead)
    assert factors.get("clinic_aov_bonus") == 0.05


def test_score_caps_at_one():
    # Pile every bonus on
    lead = _lead(
        niche="clinic_dental",
        business_website_url=None,
        business_rating=4.0,
        business_review_count=500,
    )
    score, factors = score_lead(lead)
    assert score == pytest.approx(0.45 + 0.05 + 0.05 + 0.05)
    # Doesn't exceed 1
    assert score <= 1.0


@pytest.mark.parametrize("niche,city,expected_substring", [
    ("restaurant", "Kuala Lumpur", "restaurant in Kuala Lumpur"),
    ("clinic_dental", "Penang", "dental clinic in Penang"),
    ("clinic_medical", "Johor Bahru", "medical clinic in Johor Bahru"),
    ("clinic_beauty", "Ipoh", "beauty clinic in Ipoh"),
])
def test_search_query_mapping(niche, city, expected_substring):
    assert search_query_for(niche, city) == expected_substring
