# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from this file's directory
env_path = Path(__file__).resolve().with_name(".env")
load_dotenv(dotenv_path=env_path, override=True)

API_KEY = os.getenv("API_KEY", "PUT_STUDENT_USERNAME_HERE")
API_KEY = (API_KEY or "PUT_STUDENT_USERNAME_HERE").strip()

# Debug print so you can confirm what Flask is using
print(f"[config] Loaded API_KEY = '{API_KEY}'")
