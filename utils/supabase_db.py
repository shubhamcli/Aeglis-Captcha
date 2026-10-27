import os
import requests
from fastapi import Request, HTTPException
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Fetch credentials securely
SB_URL = os.getenv("SB_API_URL")
SB_ANON_KEY = os.getenv("SB_ANON_KEY")
SB_SECRET_KEY = os.getenv("SB_SECRET_KEY")

# Fail-safe: Agar .env set nahi hai toh server start hi nahi hoga
if not all([SB_URL, SB_ANON_KEY, SB_SECRET_KEY]):
    raise ValueError("Supabase Credentials missing! Please check your .env file.")

try:
    
    # Use this ONLY for: supabase_auth.auth.sign_up() or .sign_in_with_password()
    supabase: Client = create_client(SB_URL, SB_ANON_KEY)
    
   
    # Use this for: Database CRUD (scans, profiles, credits). Bypasses RLS!
    supabase_admin: Client = create_client(SB_URL, SB_SECRET_KEY)
    
    print("Supabase Clients (Auth & Admin) initialized successfully.")

except Exception as e:
    print(f"Failed to initialize Supabase clients: {e}")
    raise e

def get_current_user(request: Request) -> str:
    """Extracts and verifies JWT Token OR Device Key to return secure user_id (Hybrid Guard)"""
    auth = request.headers.get("Authorization")
    
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
        
    token = auth[7:]
    
    try:
        # Only normal JWT will be accepted.
        user = supabase.auth.get_user(token)
        if not user.user:
            raise HTTPException(status_code=401, detail="Invalid JWT token")
        return user.user.id
            
            
    except Exception as e:
        # Backend terminal mein print karna zaroori hai debugging ke liye
        print(f"Auth Blocked: {str(e)}") 
        raise HTTPException(status_code=401, detail="Token verification failed")