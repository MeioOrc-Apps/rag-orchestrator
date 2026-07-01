from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    default_owner_username: str

    docling_base_url: str = ""
    opensearch_host: str = "http://host.docker.internal:9200"
    opensearch_index_prefix: str = "rag"
    input_dir: str = "/data/inputs"

    ollama_host: str = "http://host.docker.internal:11434"
    openrouter_api_key: str = ""

    scan_interval_minutes: int = 15
    parse_interval_minutes: int = 5
    translate_interval_minutes: int = 5
    index_interval_minutes: int = 5
    mcp_port: int = 9700

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
