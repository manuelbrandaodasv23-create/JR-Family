from app.config import Settings


def test_cloud_postgres_urls_use_installed_driver():
    for scheme in ("postgres", "postgresql"):
        settings = Settings(database_url=f"{scheme}://user:pass@db:5432/family")
        assert settings.database_url == "postgresql+psycopg://user:pass@db:5432/family"


def test_explicit_driver_and_sqlite_are_preserved():
    for url in ("postgresql+psycopg://user:pass@db/family", "sqlite:///./test.db"):
        assert Settings(database_url=url).database_url == url
