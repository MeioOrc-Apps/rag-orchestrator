from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    docling_base_url: str
    opensearch_host: str
    input_dir: str
    default_owner_username: str

    opensearch_index_prefix: str = "rag"
    scan_interval_minutes: int = 15
    parse_interval_minutes: int = 5
    translate_interval_minutes: int = 5
    index_interval_minutes: int = 5
    max_translation_retries: int = 3
    chunk_size: int = 1000
    chunk_overlap: int = 100
    enrichment_model: str = "local:qwen2.5:7b"
    ollama_host: str = "http://host.docker.internal:11434"
    mcp_port: int = 9700

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
