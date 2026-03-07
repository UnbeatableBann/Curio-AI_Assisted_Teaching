from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GOOGLE_SEARCH_API_KEY: str
    GOOGLE_CX: str
    GEMINI_API_KEY: str

    WAKEUP_WORD_PATH: str
    PICOVOICE_API_KEY: str

    FOLDER_PATH: str
    APPWRITE_API_KEY: str
    APPWRITE_PROJECT_ID: str
    APPWRITE_REGION: str
    APPWRITE_BUCKET_ID: str

    UNSPLASH_ACCESS_KEY: str

    SERPAPI_KEY: str

    # Reverie SDK for Speech-to-Text
    REVERIE_API_KEY: str
    REVERIE_APP_ID: str

    SUPABASE_URL: str
    SUPABASE_KEY: str

    model_config = SettingsConfigDict(
        env_file="../.env"
    )


settings = Settings()
