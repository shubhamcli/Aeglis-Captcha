import os
from dotenv import load_dotenv
import redis

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise ValueError("REDIS_URL is missing from .env")

REDIS_CLIENT = redis.from_url(REDIS_URL, decode_responses=True)
