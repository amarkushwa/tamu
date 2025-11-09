"""
Configuration management for Gemini Classifier
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration"""

    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    SOLANA_CLUSTER_URL = os.getenv("SOLANA_CLUSTER_URL", "https://api.devnet.solana.com")

    # Model Configuration
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
    ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "flash_v2_5")

    # Processing Configuration
    MAX_PAGES = int(os.getenv("MAX_PAGES", "100"))
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.9"))
    DUAL_VALIDATION_ENABLED = os.getenv("DUAL_VALIDATION_ENABLED", "true").lower() == "true"

    # Paths
    BASE_DIR = Path(__file__).parent.parent
    UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "data/uploads")
    CACHE_DIR = BASE_DIR / os.getenv("CACHE_DIR", "data/cache")
    AUDIT_LOG_DIR = BASE_DIR / os.getenv("AUDIT_LOG_DIR", "data/audit_logs")
    POLICY_DIR = BASE_DIR / os.getenv("POLICY_DIR", "policies")

    # Database
    DATABASE_PATH = BASE_DIR / "data" / "audit_logs.db"

    # Categories
    CATEGORIES = ["PUBLIC", "SENSITIVE", "CONFIDENTIAL", "UNSAFE"]

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []

        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required")
        if not cls.ELEVENLABS_API_KEY:
            errors.append("ELEVENLABS_API_KEY is required")
        if not cls.SOLANA_CLUSTER_URL:
            errors.append("SOLANA_CLUSTER_URL is required")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        # Create directories
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cls.AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        cls.POLICY_DIR.mkdir(parents=True, exist_ok=True)

        return True

# Validate configuration on import
Config.validate()
