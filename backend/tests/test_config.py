import pytest


REQUIRED_VARS = {
    "DATABASE_URL": "postgresql+psycopg://test:test@localhost/test",
    "DOCLING_BASE_URL": "http://localhost:5001",
    "OPENSEARCH_HOST": "http://localhost:9200",
    "INPUT_DIR": "/data/inputs",
    "DEFAULT_OWNER_USERNAME": "sergio",
}


def _clear_settings_cache():
    import importlib
    import app.config as cfg_mod
    importlib.reload(cfg_mod)


def _make_settings(monkeypatch, overrides=None):
    for key in REQUIRED_VARS:
        monkeypatch.delenv(key, raising=False)
    for key, val in REQUIRED_VARS.items():
        monkeypatch.setenv(key, val)
    if overrides:
        for key, val in overrides.items():
            if val is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, val)
    _clear_settings_cache()
    from app.config import Settings
    return Settings()


def test_config_loads_all_required_vars(monkeypatch):
    settings = _make_settings(monkeypatch)
    assert settings.database_url == REQUIRED_VARS["DATABASE_URL"]
    assert settings.docling_base_url == REQUIRED_VARS["DOCLING_BASE_URL"]
    assert settings.opensearch_host == REQUIRED_VARS["OPENSEARCH_HOST"]
    assert settings.input_dir == REQUIRED_VARS["INPUT_DIR"]
    assert settings.default_owner_username == REQUIRED_VARS["DEFAULT_OWNER_USERNAME"]


def test_config_has_correct_defaults(monkeypatch):
    settings = _make_settings(monkeypatch)
    assert settings.opensearch_index_prefix == "rag"
    assert settings.scan_interval_minutes == 15
    assert settings.parse_interval_minutes == 5
    assert settings.translate_interval_minutes == 5
    assert settings.index_interval_minutes == 5
    assert settings.max_translation_retries == 3
    assert settings.chunk_size == 1000
    assert settings.chunk_overlap == 100
    assert settings.enrichment_model == "local:qwen2.5:7b"
    assert settings.ollama_host == "http://host.docker.internal:11434"
    assert settings.mcp_port == 9700


def test_config_scan_interval_overridable(monkeypatch):
    settings = _make_settings(monkeypatch, overrides={"SCAN_INTERVAL_MINUTES": "30"})
    assert settings.scan_interval_minutes == 30


def test_config_no_lightrag_fields(monkeypatch):
    settings = _make_settings(monkeypatch)
    assert not hasattr(settings, "lightrag_base_url")
    assert not hasattr(settings, "lightrag_username")
    assert not hasattr(settings, "lightrag_password")
    assert not hasattr(settings, "lightrag_input_dir")


@pytest.mark.parametrize("missing_var", list(REQUIRED_VARS.keys()))
def test_config_fails_clearly_when_required_var_missing(monkeypatch, missing_var):
    _clear_settings_cache()
    with pytest.raises(Exception):
        _make_settings(monkeypatch, overrides={missing_var: None})
