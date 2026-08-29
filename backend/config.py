
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "Dubizzle Nysa — Car Intelligence"
    app_version: str = "1.0.0"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.7-flash"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    database_path: str = str(ROOT_DIR / "data" / "nysa.db")
    leads_csv_path: str = str(ROOT_DIR / "data" / "leads.csv")
    dataset_path: str = str(ROOT_DIR / "data" / "cars_dataset.xlsx")
    max_results: int = 8
    model_temperature: float = 0.15

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
