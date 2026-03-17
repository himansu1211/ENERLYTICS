import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# Global Configuration Constants
GLOBAL_SEED = int(os.getenv("GLOBAL_SEED", 42))
DEFAULT_TAU = float(os.getenv("DEFAULT_TAU", 0.75))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# NASA API Configuration (Not used yet as NASA API is public, but prepared)
NASA_API_KEY = os.getenv("NASA_API_KEY", "")
