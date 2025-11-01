
from pathlib import Path

import pytest

from libanaf.config import get_config, AppConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


@pytest.fixture(autouse=True)
def clear_config_cache():
    """Clear the lru_cache for get_config before each test."""
    get_config.cache_clear()


def test_load_config_from_toml(monkeypatch):
    """Test that the config is correctly loaded from a TOML file."""
    config_path = FIXTURES_DIR / "test_config.toml"
    secrets_path = FIXTURES_DIR

    monkeypatch.setenv("LIBANAF_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("LIBANAF_SECRETS_PATH", str(secrets_path))
    monkeypatch.setenv("LIBANAF_CLIENT_SECRET", "env_secret")

    config = get_config(env="test")

    assert config.auth.auth_url == "https://example.com/auth"
    assert config.auth.client_id == "toml_client_id"
    assert config.auth.client_secret == "env_secret"
    assert config.efactura.upload_url == "https://toml.example.com/upload"
    assert config.storage.download_dir == Path("/tmp/libanaf_downloads")

