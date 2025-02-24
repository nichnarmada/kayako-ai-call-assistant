from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # API Keys
    DEEPGRAM_API_KEY: str
    OPENAI_API_KEY: str
    KAYAKO_API_KEY: str | None = None  # Optional, might use basic auth instead
    
    # Service URLs
    KAYAKO_URL: str = "https://doug-test.kayako.com"
    
    # Deepgram Settings
    DEEPGRAM_STT_MODEL: str = "nova-2"
    DEEPGRAM_TTS_MODEL: str = "aura-asteria-en"
    
    # OpenAI Settings
    OPENAI_MODEL: str = "gpt-4o"
    
    # Application Settings
    APP_NAME: str = "Kayako AI Call Assistant"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings() 