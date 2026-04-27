"""Pure scoring — no I/O. Tested in isolation.

Lead fit = how badly do they need a new $2k website + $200/mo retainer?

Higher score = better target. Range 0..1.

Factors (additive, weighted):
  - No website at all                                +0.45  (biggest signal)
  - Website exists but not HTTPS                     +0.15  (outdated)
  - Website mobile_score < 60                        +0.15  (failing modern UX)
  - Website has no booking widget detected           +0.10  (booking is a 6c demo highlight)
  - Google rating in [3.5, 4.5]                      +0.05  (cares about rep, room to improve)
  - Google review_count >= 50                        +0.05  (active business, viable lead)
  - Niche-specific bonus (clinics: +0.05)            +0.05  (higher-AOV than restaurants)

Cap at 1.0. Floor at 0.0.
"""
from prospect_agent.models import Lead


def score_lead(lead: Lead) -> tuple[float, dict]:
    """Return (fit_score, factors_breakdown)."""
    factors: dict[str, float] = {}

    # 1. Website presence — biggest signal
    if not lead.business_website_url:
        factors["no_website"] = 0.45
    else:
        # Penalize outdated sites (existence is fine, condition matters)
        if lead.website.https is False:
            factors["no_https"] = 0.15
        if lead.website.mobile_score is not None and lead.website.mobile_score < 60:
            factors["poor_mobile"] = 0.15
        if lead.website.has_booking is False:
            factors["no_booking"] = 0.10

    # 2. Reputation sweet spot — they care, but aren't already perfect
    if lead.business_rating is not None and 3.5 <= lead.business_rating <= 4.5:
        factors["rating_in_band"] = 0.05

    # 3. Active business — signal that outreach won't be wasted
    if lead.business_review_count is not None and lead.business_review_count >= 50:
        factors["active_business"] = 0.05

    # 4. Niche bonus — clinics have higher AOV than restaurants
    if lead.niche.startswith("clinic_"):
        factors["clinic_aov_bonus"] = 0.05

    score = sum(factors.values())
    score = max(0.0, min(1.0, score))
    return score, factors


def search_query_for(niche: str, city: str) -> str:
    """Map niche + city to a Google Maps text-search query."""
    niche_term = {
        "restaurant": "restaurant",
        "clinic_dental": "dental clinic",
        "clinic_medical": "medical clinic",
        "clinic_beauty": "beauty clinic",
    }.get(niche, niche)
    return f"{niche_term} in {city}"
