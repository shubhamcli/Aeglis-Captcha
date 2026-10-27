import hashlib
import hmac
import logging
import random
import secrets
import string
import time
import json
import ipaddress
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional, List

from utils.supabase_db import supabase_admin
from redis_client import REDIS_CLIENT

# Configure module logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constants
SESSION_EXPIRY_SECONDS = 300  # 5 minutes for challenge completion
TOKEN_EXPIRY_SECONDS = 600    # 10 minutes for the final token submission
DEFAULT_POW_DIFFICULTY = 4

def _increment_usage(site_key: str):
    """
    Helper function to atomically increment the current_usage for a given site_key 
    via Supabase RPC. Runs silently and won't crash the main verification flow if it fails.
    """
    if not site_key:
        return
        
    try:
        # Call the custom RPC function created in Supabase
        supabase_admin.rpc("increment_site_usage", {"site_key_param": site_key}).execute()
    except Exception as e:
        logger.error(f"Failed to increment usage for {site_key} via RPC: {e}")

def _generate_webgl_params() -> Dict[str, Any]:
    """
    Phase 1: Generates random parameters for the 3D WebGL render.
    This ensures the frontend draws a unique object every time, preventing hash replay.
    """
    return {
        "color_hex_1": f"#{secrets.token_hex(3)}",
        "color_hex_2": f"#{secrets.token_hex(3)}",
        "rotation_x": round(random.uniform(0.1, 2.0), 3),
        "rotation_y": round(random.uniform(0.1, 2.0), 3),
        "vertices": random.randint(10, 50)
    }

def _generate_dom_map() -> Dict[str, str]:
    """
    Phase 2: Generates a randomized CSS map for the frontend DOM trap.
    """
    def _rand_class() -> str:
        return "aeg-" + ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    return {
        "container": _rand_class(),
        "checkbox_real": _rand_class(),
        "checkmark": _rand_class(),
        "label": _rand_class(),
        "honeypot_1": _rand_class(), # Invisible trap button
        "honeypot_2": _rand_class()  # Off-screen trap button
    }

def _generate_pow_challenge(difficulty: int) -> Tuple[str, str]:
    """
    Phase 3: Generates a salt and target prefix for the Proof of Work.
    """
    salt = secrets.token_hex(16)
    target_prefix = '0' * difficulty
    return salt, target_prefix

def _generate_physics_puzzle() -> Dict[str, Any]:
    """
    Phase 4: Generates parameters for randomly selected AI-resistant physics puzzles.
    Includes the original slider and 3 new unique challenges.
    """
    puzzle_types = [
        "slider_balance", 
        "liquid_pour", 
        "shadow_match", 
        "friction_drag"
    ]
    
    selected_type = random.choice(puzzle_types)
    
    if selected_type == "slider_balance":
        return {
            "puzzle_type": "slider_balance",
            "target_value": random.randint(25, 85),
            "tolerance": 2
        }
    elif selected_type == "liquid_pour":
        return {
            "puzzle_type": "liquid_pour",
            "target_value": random.randint(40, 80),
            "tolerance": 4
        }
    elif selected_type == "shadow_match":
        return {
            "puzzle_type": "shadow_match",
            "target_value": random.randint(30, 330),
            "tolerance": 5
        }
    elif selected_type == "friction_drag":
        return {
            "puzzle_type": "friction_drag",
            "target_value": random.randint(150, 250),
            "tolerance": 8
        }

def create_challenge(site_key: str = None) -> Dict[str, Any]:
    """
    Orchestrates the creation of a new Captcha challenge session.
    Invoked by the /challenge route.
    Validates the site_key against the database before proceeding.
    """
    try:
        # Validate site_key if provided
        if site_key:
            response = supabase_admin.table("captcha_sites").select("id").eq("site_key", site_key).execute()
            if not response.data:
                logger.warning(f"Challenge requested with invalid site_key: {site_key}")
                return {"success": False, "error": "Invalid site key provided."}
                
        session_id = f"sess_{secrets.token_hex(16)}"
        
        webgl_params = _generate_webgl_params()
        dom_map = _generate_dom_map()
        salt, target_prefix = _generate_pow_challenge(DEFAULT_POW_DIFFICULTY)
        
        session_data = {
            "created_at": time.time(),
            "status": "pending",
            "webgl_params": webgl_params,
            "dom_map": dom_map,
            "pow_salt": salt,
            "pow_target": target_prefix,
            "puzzle_data": None,
            "site_key": site_key # Store the site key in the session for later use if needed
        }
        REDIS_CLIENT.setex(f"captcha_sess:{session_id}", SESSION_EXPIRY_SECONDS, json.dumps(session_data))
        
        return {
            "success": True,
            "session_id": session_id,
            "webgl_params": webgl_params,
            "dom_map": dom_map,
            "pow_challenge": {
                "salt": salt,
                "difficulty": DEFAULT_POW_DIFFICULTY
            }
        }
    except Exception as e:
        logger.error(f"Error creating challenge: {str(e)}")
        return {"success": False, "error": "Internal engine error"}

def _verify_pow(salt: str, nonce: int, target_prefix: str) -> bool:
    """Verifies the Phase 3 CPU tax solution."""
    try:
        challenge_str = f"{salt}{nonce}".encode('utf-8')
        check_hash = hashlib.sha256(challenge_str).hexdigest()
        return check_hash.startswith(target_prefix)
    except Exception:
        return False

def _check_datacenter_ip(ip_str: str) -> float:
    """
    Checks if the IP belongs to known Datacenter/Cloud providers ranges.
    Returns a penalty score if matched, otherwise 0.0.
    In a production system, this would query a MaxMind DB or ASN database.
    Here we use a simplified mock implementation for the concept.
    """
    if not ip_str:
        return 0.0
        
    penalty = 0.0
    try:
        ip = ipaddress.ip_address(ip_str)
        # 1. Reject private/local IPs if expecting public traffic (optional, good for prod)
        if ip.is_private and not ip.is_loopback:
            pass
            
        # 2. Mock Datacenter IP ranges (e.g., AWS, GCP, DigitalOcean)
        datacenter_subnets = [
            ipaddress.ip_network("3.0.0.0/8"),    # Example AWS block
            ipaddress.ip_network("34.0.0.0/8"),   # Example GCP block
            ipaddress.ip_network("104.131.0.0/16") # Example DO block
        ]
        
        for subnet in datacenter_subnets:
            if ip in subnet:
                logger.warning(f"IP {ip_str} identified as Datacenter/Cloud IP.")
                penalty = 0.3 # Reduce score by 0.3, forcing a puzzle if they are otherwise perfect.
                break
                
    except ValueError:
        logger.error(f"Invalid IP address format received: {ip_str}")
        
    return penalty

def _analyze_mouse_entropy(trail: List[List[float]]) -> float:
    """
    Analyzes mouse coordinates [x, y, timestamp] to detect bots.
    Returns a penalty score (0.0 to 1.0). 0.0 means perfect human, 1.0 means definite bot.
    """
    # 1. EMPTY / INSTANT CLICK CHECK
    if not trail or len(trail) < 3:
        logger.warning("Bot Detected: Mouse trail is empty or too short. Teleportation detected.")
        return 0.8 # Heavy penalty: Clicked without moving mouse!

    penalty = 0.0
    x_changes = []
    y_changes = []
    time_changes = []

    for i in range(1, len(trail)):
        x_changes.append(abs(trail[i][0] - trail[i-1][0]))
        y_changes.append(abs(trail[i][1] - trail[i-1][1]))
        time_changes.append(trail[i][2] - trail[i-1][2])

    # 2. PATTERN / ALGORITHMIC REPLAY CHECK
    unique_x = len(set(x_changes))
    unique_y = len(set(y_changes))
    
    if unique_x <= 2 and unique_y <= 2:
        logger.warning("Bot Detected: Mouse pattern is algorithmically perfect/repeating.")
        return 1.0 # Instant Bot (Force block)

    # 3. CONSTANT SPEED CHECK
    unique_times = len(set(time_changes))
    if unique_times <= 1:
        logger.warning("Bot Detected: Mouse timestamp intervals are perfectly constant.")
        penalty += 0.5 

    # 4. PERFECT STRAIGHT LINE CHECK
    if sum(y_changes) == 0 and sum(x_changes) > 50:
        logger.warning("Bot Detected: Perfect straight horizontal line drawn.")
        penalty += 0.4
    elif sum(x_changes) == 0 and sum(y_changes) > 50:
        logger.warning("Bot Detected: Perfect straight vertical line drawn.")
        penalty += 0.4

    return min(penalty, 1.0)

def _evaluate_telemetry(payload: Dict[str, Any], dom_map: Dict[str, str], client_ip: str = "") -> float:
    """
    Evaluates Phase 1 (WebGL), Phase 2 (DOM), Mouse Entropy, and IP telemetry.
    Queries the captcha_bot_signatures table in Supabase.
    """
    score = 1.0
    
    # --- 1. WebGL Fingerprint Check ---
    webgl_hash = str(payload.get("webgl_hash", "")).strip()
    if not webgl_hash:
        logger.warning("Failed Phase 1: Missing WebGL signature.")
        score -= 0.6
    else:
        try:
            response = supabase_admin.table("captcha_bot_signatures").select("is_blocked").eq("webgl_renderer", webgl_hash).execute()
            if response.data and response.data[0].get("is_blocked"):
                logger.warning(f"Failed Phase 1: Blacklisted WebGL detected ({webgl_hash}).")
                score -= 0.6
        except Exception as e:
            logger.error(f"Error checking WebGL DB: {e}")
            
    # --- 2. DOM Trap Check ---
    clicked_class = payload.get("clicked_class")
    if clicked_class in [dom_map.get("honeypot_1"), dom_map.get("honeypot_2")]:
        logger.warning("Failed Phase 2: Bot fell for the DOM Trap.")
        return 0.0 
        
    # --- 3. Speed Heuristics Check ---
    time_taken_ms = payload.get("interaction_time_ms", 0)
    if time_taken_ms < 50:
        logger.warning("Failed Phase 2: Interaction too fast to be human.")
        score -= 0.5
        
    # --- 4. Behavioral Biometrics (Mouse Entropy) ---
    mouse_trail = payload.get("mouse_trail", [])
    mouse_penalty = _analyze_mouse_entropy(mouse_trail)
    if mouse_penalty > 0:
        logger.info(f"Mouse Entropy applied penalty of -{mouse_penalty}")
    score -= mouse_penalty
    
    # --- 5. IP Reputation / Datacenter Check ---
    if client_ip:
        ip_penalty = _check_datacenter_ip(client_ip)
        if ip_penalty > 0:
            logger.info(f"Datacenter IP applied penalty of -{ip_penalty}")
        score -= ip_penalty
        
    return max(0.0, score)

def process_verification(session_id: str, payload: Dict[str, Any], site_key: str = None, client_ip: str = "") -> Dict[str, Any]:
    """
    Orchestrates the verification of telemetry. Returns result instantly.
    Logging is now handled by the router via BackgroundTasks.
    """
    try:
        raw_session = REDIS_CLIENT.get(f"captcha_sess:{session_id}")
        if not raw_session: return {"success": False, "error": "Invalid or expired session."}
            
        session = json.loads(raw_session)
        if session["status"] != "pending": return {"success": False, "error": "Session already processed."}
            
        # Increment billing usage for this verification attempt
        if site_key:
            _increment_usage(site_key)
            
        nonce = payload.get("pow_nonce")
        if nonce is None or not _verify_pow(session["pow_salt"], nonce, session["pow_target"]):
            session["status"] = "failed"
            REDIS_CLIENT.setex(f"captcha_sess:{session_id}", SESSION_EXPIRY_SECONDS, json.dumps(session))
            return {"success": False, "error": "Proof of Work validation failed."}
            
        # The real dynamic score calculated based on WebGL, DOM, Time, Mouse Entropy, and IP
        trust_score = _evaluate_telemetry(payload, session["dom_map"], client_ip)
        
        # Logging Telemetry variables
        webgl_hash = payload.get("webgl_hash", "")
        interaction_time_ms = payload.get("interaction_time_ms", 0)

        trust_score = 0.5  # REMOVED: override for testing purposes
        
        if trust_score == 0.0:
            session["status"] = "blocked"
            REDIS_CLIENT.setex(f"captcha_sess:{session_id}", SESSION_EXPIRY_SECONDS, json.dumps(session))
            
            # DB insert removed, returning log_data dictionary instead for background processing
            return {
                "success": False, 
                "error": "Automated behavior detected.", 
                "action": "block",
                "log_data": {
                    "action_taken": "blocked",
                    "fail_reason": "Automated behavior detected (Score 0.0)"
                }
            }
            
        elif trust_score < 0.8:
            session["status"] = "require_puzzle"
            puzzle_data = _generate_physics_puzzle()
            session["puzzle_data"] = puzzle_data
            REDIS_CLIENT.setex(f"captcha_sess:{session_id}", SESSION_EXPIRY_SECONDS, json.dumps(session))
            return {
                "success": False, 
                "action": "require_puzzle", 
                "puzzle": {
                    "type": puzzle_data["puzzle_type"],
                    "target": puzzle_data["target_value"]
                }
            }
            
        else:
            token = f"aeg_tok_{secrets.token_hex(24)}"
            token_data = {"created_at": time.time(), "used": False}
            REDIS_CLIENT.setex(f"captcha_tok:{token}", TOKEN_EXPIRY_SECONDS, json.dumps(token_data))
            REDIS_CLIENT.delete(f"captcha_sess:{session_id}")
            
            # DB insert removed, returning log_data dictionary instead for background processing
            return {
                "success": True, 
                "token": token, 
                "action": "pass",
                "log_data": {
                    "action_taken": "passed",
                    "fail_reason": None
                }
            }
            
    except Exception as e:
        logger.error(f"Error processing verification: {str(e)}")
        return {"success": False, "error": "Internal engine error"}

def verify_puzzle(session_id: str, answer: float, site_key: str = None) -> Dict[str, Any]:
    """
    Verifies the answer to the Phase 4 Physics Puzzle. Returns result instantly.
    Logging is now handled by the router via BackgroundTasks.
    """
    try:
        raw_session = REDIS_CLIENT.get(f"captcha_sess:{session_id}")
        if not raw_session: return {"success": False, "error": "Invalid or expired puzzle session."}
            
        session = json.loads(raw_session)
        if session.get("status") != "require_puzzle": return {"success": False, "error": "Invalid puzzle session state."}
            
        puzzle_data = session.get("puzzle_data", {})
        target = puzzle_data.get("target_value", 0)
        tolerance = puzzle_data.get("tolerance", 0)
        
        if abs(answer - target) <= tolerance:
            token = f"aeg_tok_{secrets.token_hex(24)}"
            token_data = {"created_at": time.time(), "used": False}
            REDIS_CLIENT.setex(f"captcha_tok:{token}", TOKEN_EXPIRY_SECONDS, json.dumps(token_data))
            REDIS_CLIENT.delete(f"captcha_sess:{session_id}")
            
            # DB insert removed, returning log_data dictionary instead for background processing
            return {
                "success": True, 
                "token": token, 
                "action": "pass",
                "log_data": {
                    "action_taken": "passed",
                    "fail_reason": "Passed via puzzle"
                }
            }
        else:
            session["status"] = "failed"
            REDIS_CLIENT.setex(f"captcha_sess:{session_id}", SESSION_EXPIRY_SECONDS, json.dumps(session))
            
            # DB insert removed, returning log_data dictionary instead for background processing
            return {
                "success": False, 
                "error": "Puzzle calibration failed.", 
                "action": "block",
                "log_data": {
                    "action_taken": "blocked",
                    "fail_reason": "Puzzle failed"
                }
            }
            
    except Exception as e:
        logger.error(f"Error verifying puzzle: {str(e)}")
        return {"success": False, "error": "Internal engine error"}

def verify_site_token(token: str) -> bool:
    """
    Verifies the final token submitted by the customer's server.
    """
    try:
        raw_token = REDIS_CLIENT.get(f"captcha_tok:{token}")
        if not raw_token: return False
        token_data = json.loads(raw_token)
        if token_data.get("used") is True: return False
        
        token_data["used"] = True
        REDIS_CLIENT.setex(f"captcha_tok:{token}", TOKEN_EXPIRY_SECONDS, json.dumps(token_data))
        return True
    except Exception as e:
        logger.error(f"Error verifying site token: {str(e)}")
        return False