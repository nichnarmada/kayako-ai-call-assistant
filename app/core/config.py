from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # API Keys
    DEEPGRAM_API_KEY: str
    OPENAI_API_KEY: str
    TWILIO_AUTH_TOKEN: str
    
    # Kayako Credentials
    KAYAKO_EMAIL: str
    KAYAKO_PASSWORD: str
    KAYAKO_URL: str = "https://doug-test.kayako.com"
    
    # Deepgram Settings
    DEEPGRAM_STT_MODEL: str = "nova-3"
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