from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # API Configuration
    API_TITLE: str = "SPC Suggestion API"
    API_VERSION: str = "1.0.0"
    
    # Gemini Configuration
    GOOGLE_API_KEY: str
    # CORRECT MODEL NAMES:
    # - "gemini-1.5-pro-latest" (most capable, slower)
    # - "gemini-1.5-flash-latest" (faster, good for most tasks)
    # - "gemini-pro" (older, stable)
    GEMINI_MODEL: str = "gemini-2.5-pro"  # Changed from "gemini-1.5-pro"
    GEMINI_TEMPERATURE: float = 0.2
    GEMINI_MAX_TOKENS: int = 4096
    
    # CORS Configuration
    ALLOWED_ORIGINS: list = [
        "*",
        "https://*.dynamics.com",
        "https://*.crm.dynamics.com",
        "http://localhost:3000"  # For local testing
    ]
    
    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = 10
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()

# from pydantic_settings import BaseSettings
# from functools import lru_cache

# class Settings(BaseSettings):
#     # API Configuration
#     API_TITLE: str = "SPC Suggestion API"
#     API_VERSION: str = "1.0.0"
    
#     # Gemini Configuration
#     GOOGLE_API_KEY: str
#     GEMINI_MODEL: str = "gemini-1.5-pro"
#     GEMINI_TEMPERATURE: float = 0.2
#     GEMINI_MAX_TOKENS: int = 4096
    
#     # CORS Configuration
#     ALLOWED_ORIGINS: list = [
#         "*",
#         "https://*.dynamics.com",
#         "https://*.crm.dynamics.com",
#         "http://localhost:3000"  # For local testing
#     ]
    
#     # Rate Limiting
#     MAX_REQUESTS_PER_MINUTE: int = 10
    
#     class Config:
#         env_file = ".env"
#         case_sensitive = True

# @lru_cache()
# def get_settings():
#     return Settings()