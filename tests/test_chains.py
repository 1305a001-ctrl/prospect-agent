from prospect_agent.chains import detect_chains, name_root, normalize, root_domain, token_prefix


def test_root_domain_basic():
    assert root_domain("https://mediviron.com.my/branch1") == "mediviron"
    assert root_domain("https://www.bp-healthcare.com/about") == "bp-healthcare"
    assert root_domain("https://example.org") == "example"
    assert root_domain(None) is None
    assert root_domain("") is None


def test_root_domain_strips_platforms():
    """Many leads share facebook/instagram/sevenrooms as 'website' — not a real chain."""
    assert root_domain("https://www.facebook.com/MyClinic") is None
    assert root_domain("https://instagram.com/myclinic") is None
    assert root_domain("https://www.sevenrooms.com/reservations/x/goog") is None
    assert root_domain("https://wa.me/60123456") is None
    assert root_domain("https://linktr.ee/myclinic") is None


def test_name_root_with_separator():
    assert name_root("Klinik Mediviron • The Grand Subang") == "Klinik Mediviron"
    assert name_root("Klinik Mediviron - PJ Old Town") == "Klinik Mediviron"
    assert name_root("BP Healthcare | Bangsar") == "BP Healthcare"
    assert name_root("Cafe @ KLCC") == "Cafe"


def test_name_root_returns_none_when_no_separator():
    assert name_root("Random Standalone Cafe") is None
    assert name_root("Klinik X") is None  # right side too short → reject


def test_normalize():
    assert normalize("Klinik Mediviron • PJ") == "klinik mediviron pj"
    assert normalize("Café & Bistro") == "caf bistro"


def test_token_prefix_skips_filler():
    # 'klinik' is in PARENT_HINTS so it gets dropped
    assert token_prefix("Klinik Mediviron Setia") == "mediviron setia"
    assert token_prefix("The Grand Hotel") == "grand hotel"


def test_detect_chains_by_name_root():
    leads = [
        {"id": "1", "business_name": "Klinik Mediviron • PJ", "niche": "clinic_medical",
         "geo_country": "MY", "business_website_url": None, "business_review_count": 100},
        {"id": "2", "business_name": "Klinik Mediviron • Subang", "niche": "clinic_medical",
         "geo_country": "MY", "business_website_url": None, "business_review_count": 200},
        {"id": "3", "business_name": "Klinik Mediviron • KL", "niche": "clinic_medical",
         "geo_country": "MY", "business_website_url": None, "business_review_count": 50},
        {"id": "4", "business_name": "Random Cafe", "niche": "restaurant",
         "geo_country": "MY", "business_website_url": None, "business_review_count": 30},
    ]
    out = detect_chains(leads)
    # All three Mediviron in one chain
    assert out["1"]["chain_name"] == "Klinik Mediviron"
    assert out["2"]["chain_name"] == "Klinik Mediviron"
    assert out["3"]["chain_name"] == "Klinik Mediviron"
    # Parent = most reviews → id=2
    assert out["2"]["chain_role"] == "parent"
    assert out["1"]["chain_role"] == "branch"
    assert out["3"]["chain_role"] == "branch"
    # Standalone
    assert out["4"]["chain_role"] == "standalone"
    assert out["4"]["chain_name"] is None


def test_detect_chains_by_shared_domain():
    """Two clinics sharing a website domain are siblings even without a name pattern."""
    leads = [
        {"id": "1", "business_name": "Acme Clinic", "niche": "clinic_medical",
         "geo_country": "MY", "business_website_url": "https://chain.com.my/branch-a",
         "business_review_count": 80},
        {"id": "2", "business_name": "Other Clinic", "niche": "clinic_medical",
         "geo_country": "MY", "business_website_url": "https://chain.com.my/branch-b",
         "business_review_count": 120},
    ]
    out = detect_chains(leads)
    assert out["1"]["chain_role"] in ("parent", "branch")
    assert out["2"]["chain_role"] in ("parent", "branch")
    assert out["1"]["chain_name"] == out["2"]["chain_name"]
    # Parent = more reviews
    assert out["2"]["chain_role"] == "parent"


def test_singleton_stays_standalone():
    leads = [
        {"id": "1", "business_name": "Klinik Solo", "niche": "clinic_medical",
         "geo_country": "MY", "business_website_url": None, "business_review_count": 50},
    ]
    out = detect_chains(leads)
    assert out["1"]["chain_role"] == "standalone"


def test_empty_input():
    assert detect_chains([]) == {}
