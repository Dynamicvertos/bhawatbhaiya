import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

# Digital Signature Secret (for HMAC signing of test reports)
SIGNATURE_SECRET = os.getenv("SIGNATURE_SECRET", "ncb-forensics-tamper-evident-secret-2026")

# Server Settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
BASE_URL = os.getenv("BASE_URL", os.getenv("RENDER_EXTERNAL_URL", "https://bhawatbhaiya.onrender.com"))

# Local Directories
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
CERTIFICATES_DIR = DATA_DIR / "certificates"
SQLITE_DB_PATH = DATA_DIR / "local_tests.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)
CERTIFICATES_DIR.mkdir(exist_ok=True)

def is_supabase_configured() -> bool:
    """Returns True if Supabase URL and Key are set and not placeholder values."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    if "your-project" in SUPABASE_URL or "your-key" in SUPABASE_KEY:
        return False
    return True

