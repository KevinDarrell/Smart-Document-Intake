import os

from openai import OpenAI

DB_PATH = os.environ.get("DB_PATH", "intake.db")
MODEL = "deepseek-chat"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY or "missing-key",
    base_url="https://api.deepseek.com",
)


def require_deepseek_key():
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")
