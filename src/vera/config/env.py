import os
from pathlib import Path

def load_dotenv(env_path: str = ".env") -> None:
    """Load environment variables from a .env file."""
    path = Path(env_path)
    if not path.exists():
        return
        
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Use os.environ.setdefault so we don't overwrite existing env vars
                os.environ.setdefault(key, val)

class Config:
    @property
    def gemini_api_key(self) -> str | None:
        return os.environ.get("GEMINI_API_KEY")

# Initialize and load .env once upon module import
load_dotenv()
config = Config()
