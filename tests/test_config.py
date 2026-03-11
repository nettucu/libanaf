from pathlib import Path

import pytest

from libanaf.config import Settings, get_settings, save_tokens

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the lru_cache for get_settings before each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_load_settings_from_env_file(tmp_path, monkeypatch):
    """Test that Settings loads from a .env file pointed to by LIBANAF_ENV_FILE."""
    env_file = tmp_path / ".env.test"
    env_file.write_text(
        "LIBANAF_AUTH__CLIENT_ID=test_client\n"
        "LIBANAF_AUTH__CLIENT_SECRET=test_secret\n"
        "LIBANAF_AUTH__REDIRECT_URI=https://localhost:8000/callback\n"
    )
    monkeypatch.setenv("LIBANAF_ENV_FILE", str(env_file))

    settings = get_settings()

    assert settings.auth.client_id == "test_client"
    assert settings.auth.client_secret == "test_secret"
    assert settings.auth.redirect_uri == "https://localhost:8000/callback"


def test_settings_anaf_defaults(tmp_path, monkeypatch):
    """Test that Settings has correct ANAF default endpoint values."""
    env_file = tmp_path / ".env.test"
    env_file.write_text(
        "LIBANAF_AUTH__CLIENT_ID=x\n"
        "LIBANAF_AUTH__CLIENT_SECRET=y\n"
        "LIBANAF_AUTH__REDIRECT_URI=https://localhost\n"
    )
    monkeypatch.setenv("LIBANAF_ENV_FILE", str(env_file))

    settings = get_settings()

    assert settings.auth.auth_url == "https://logincert.anaf.ro/anaf-oauth2/v1/authorize"
    assert settings.efactura.download_url == "https://api.anaf.ro/prod/FCTEL/rest/descarcare"
    assert settings.retry.count == 3
    assert settings.retry.delay == 5
    assert settings.retry.backoff_factor == 2


def test_save_tokens(tmp_path, monkeypatch):
    """Test save_tokens writes to the correct env file."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LIBANAF_AUTH__CLIENT_ID=test\n"
        "LIBANAF_AUTH__CLIENT_SECRET=secret\n"
        "LIBANAF_AUTH__REDIRECT_URI=https://localhost\n"
    )
    monkeypatch.setenv("LIBANAF_ENV_FILE", str(env_file))

    save_tokens({"access_token": "new_access", "refresh_token": "new_refresh"})

    content = env_file.read_text()
    assert "LIBANAF_CONNECTION__ACCESS_TOKEN" in content
    assert "new_access" in content
    assert "LIBANAF_CONNECTION__REFRESH_TOKEN" in content
    assert "new_refresh" in content


def test_get_settings_caching(tmp_path, monkeypatch):
    """Test get_settings() returns same instance and cache can be cleared."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LIBANAF_AUTH__CLIENT_ID=test\n"
        "LIBANAF_AUTH__CLIENT_SECRET=secret\n"
        "LIBANAF_AUTH__REDIRECT_URI=https://localhost\n"
    )
    monkeypatch.setenv("LIBANAF_ENV_FILE", str(env_file))

    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

    get_settings.cache_clear()
    s3 = get_settings()
    assert s3 is not s1
