import pytest


REQUIRED_VARS = {
    "DATABASE_URL": "postgresql+psycopg://test:test@localhost/test",
    "DEFAULT_OWNER_USERNAME": "sergio",
}


def _clear_settings_cache():
    import importlib
    import app.config as cfg_mod
    importlib.reload(cfg_mod)


_OPTIONAL_VARS_TO_CLEAR = [
    "OPENSEARCH_HOST", "DOCLING_BASE_URL",
    "OLLAMA_HOST", "OPENROUTER_API_KEY",
    "OPENSEARCH_INDEX_PREFIX", "SCAN_INTERVAL_MINUTES", "PARSE_INTERVAL_MINUTES",
    "TRANSLATE_INTERVAL_MINUTES", "INDEX_INTERVAL_MINUTES", "MCP_PORT",
]


def _make_settings(monkeypatch, overrides=None):
    for key in REQUIRED_VARS:
        monkeypatch.delenv(key, raising=False)
    for key in _OPTIONAL_VARS_TO_CLEAR:
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


def test_config_loads_required_vars(monkeypatch):
    settings = _make_settings(monkeypatch)
    assert settings.database_url == REQUIRED_VARS["DATABASE_URL"]
    assert settings.default_owner_username == REQUIRED_VARS["DEFAULT_OWNER_USERNAME"]


def test_config_has_correct_defaults(monkeypatch):
    settings = _make_settings(monkeypatch)
    assert settings.opensearch_host == "http://host.docker.internal:9200"
    assert settings.opensearch_index_prefix == "rag"
    assert settings.docling_base_url == ""
    assert settings.ollama_host == "http://host.docker.internal:11434"
    assert settings.openrouter_api_key == ""
    assert settings.scan_interval_minutes == 15
    assert settings.parse_interval_minutes == 5
    assert settings.translate_interval_minutes == 5
    assert settings.index_interval_minutes == 5
    assert settings.mcp_port == 9700


def test_config_optional_vars_overridable(monkeypatch):
    settings = _make_settings(monkeypatch, overrides={
        "OPENSEARCH_HOST": "http://192.168.1.10:9200",
        "SCAN_INTERVAL_MINUTES": "30",
        "OPENROUTER_API_KEY": "sk-or-test",
    })
    assert settings.opensearch_host == "http://192.168.1.10:9200"
    assert settings.scan_interval_minutes == 30
    assert settings.openrouter_api_key == "sk-or-test"


def test_config_no_lightrag_fields(monkeypatch):
    settings = _make_settings(monkeypatch)
    assert not hasattr(settings, "lightrag_base_url")
    assert not hasattr(settings, "lightrag_username")
    assert not hasattr(settings, "lightrag_password")
    assert not hasattr(settings, "lightrag_input_dir")


def test_config_no_pipeline_fields_in_config(monkeypatch):
    settings = _make_settings(monkeypatch)
    assert not hasattr(settings, "max_translation_retries")
    assert not hasattr(settings, "chunk_size")
    assert not hasattr(settings, "chunk_overlap")
    assert not hasattr(settings, "enrichment_model")
    assert not hasattr(settings, "parse_batch_size")
    assert not hasattr(settings, "input_dir")


@pytest.mark.parametrize("missing_var", list(REQUIRED_VARS.keys()))
def test_config_fails_when_required_var_missing(monkeypatch, missing_var):
    _clear_settings_cache()
    with pytest.raises(Exception):
        _make_settings(monkeypatch, overrides={missing_var: None})
