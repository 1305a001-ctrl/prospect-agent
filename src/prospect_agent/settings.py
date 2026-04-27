from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    aicore_db_url: str = ""

    # Google Maps Places API (https://developers.google.com/maps/documentation/places/web-service)
    google_maps_api_key: str = ""

    # Discovery scope — comma-separated for env override
    # Niches: restaurant | clinic_dental | clinic_medical | clinic_beauty
    niches: str = "restaurant,clinic_dental,clinic_medical,clinic_beauty"
    # Malaysian cities to scan
    cities: str = "Kuala Lumpur,Petaling Jaya,Subang Jaya,Penang,Johor Bahru,Ipoh,Malacca"
    # Country code for Places search
    country: str = "MY"

    # Per (niche × city) result cap. Places API returns up to 60 (3 pages × 20).
    max_results_per_query: int = 60

    # Politeness — wait between API calls
    request_delay_ms: int = 200

    # Optional: scrape lead website to enrich score (https / mobile / booking)
    enrich_websites: bool = True
    website_fetch_timeout_seconds: int = 10

    # Sentry
    sentry_dsn: str = ""

    @property
    def niche_list(self) -> list[str]:
        return [n.strip() for n in self.niches.split(",") if n.strip()]

    @property
    def city_list(self) -> list[str]:
        return [c.strip() for c in self.cities.split(",") if c.strip()]


settings = Settings()
