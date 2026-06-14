from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    docling_base_url: str
    lightrag_base_url: str
    lightrag_username: str
    lightrag_password: str
    lightrag_input_dir: str
    scan_interval_minutes: int = 30
    default_owner_username: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
