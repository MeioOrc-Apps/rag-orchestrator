import pytest


REQUIRED_VARS = {
    "DATABASE_URL": "postgresql+psycopg://test:test@localhost/test",
    "DOCLING_BASE_URL": "http://localhost:5001",
    "LIGHTRAG_BASE_URL": "http://localhost:9621",
    "LIGHTRAG_USERNAME": "sergio",
    "LIGHTRAG_PASSWORD": "secret",
    "LIGHTRAG_INPUT_DIR": "/data/inputs",
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
    assert settings.lightrag_base_url == REQUIRED_VARS["LIGHTRAG_BASE_URL"]
    assert settings.lightrag_username == REQUIRED_VARS["LIGHTRAG_USERNAME"]
    assert settings.lightrag_password == REQUIRED_VARS["LIGHTRAG_PASSWORD"]
    assert settings.lightrag_input_dir == REQUIRED_VARS["LIGHTRAG_INPUT_DIR"]
    assert settings.default_owner_username == REQUIRED_VARS["DEFAULT_OWNER_USERNAME"]


def test_config_has_default_scan_interval(monkeypatch):
    settings = _make_settings(monkeypatch)
    assert settings.scan_interval_minutes == 30


def test_config_scan_interval_overridable(monkeypatch):
    settings = _make_settings(monkeypatch, overrides={"SCAN_INTERVAL_MINUTES": "15"})
    assert settings.scan_interval_minutes == 15


@pytest.mark.parametrize("missing_var", list(REQUIRED_VARS.keys()))
def test_config_fails_clearly_when_required_var_missing(monkeypatch, missing_var):
    _clear_settings_cache()
    with pytest.raises(Exception):
        _make_settings(monkeypatch, overrides={missing_var: None})
