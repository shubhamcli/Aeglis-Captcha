#!/usr/bin/env python3
"""Generate a polished project README.md for the Aeglis backend."""

from __future__ import annotations

import ast
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parent
MAIN_FILE = ROOT / "main.py"
OUTPUT_FILE = ROOT / "README.md"

PROJECT = {
    "name": "Aeglis",
    "tagline": "Bot protection and CAPTCHA verification for modern web products",
    "summary": (
        "Aeglis is a production-ready captcha and bot-protection backend built with "
        "FastAPI. It issues adaptive verification challenges, validates Proof of Work, "
        "checks telemetry and behavioral signals, and issues signed tokens for trusted "
        "user sessions."
    ),
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_fastapi_metadata(source: str):
    tree = ast.parse(source)
    title = "Aeglis Captcha API v1"
    description = "Independent Captcha Engine with Self-Routing"

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "FastAPI":
                for keyword in node.keywords:
                    if keyword.arg == "title":
                        title = ast.literal_eval(keyword.value)
                    if keyword.arg == "description":
                        description = ast.literal_eval(keyword.value)
                break

    routes = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute):
                continue

            method = decorator.func.attr.upper()
            if method not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                continue

            if not decorator.args:
                continue

            path = ast.literal_eval(decorator.args[0])
            summary = None
            for keyword in decorator.keywords:
                if keyword.arg == "summary":
                    summary = ast.literal_eval(keyword.value)
                    break

            routes.append(
                {
                    "method": method,
                    "path": path,
                    "summary": summary or node.name.replace("_", " ").title(),
                }
            )

    return {"title": title, "description": description, "routes": routes}


def make_env_block() -> str:
    return dedent(
        """
        REDIS_URL=redis://localhost:6379/0
        SB_API_URL=https://your-project.supabase.co
        SB_ANON_KEY=your-anon-key
        SB_SECRET_KEY=your-service-role-key
        """
    ).strip()


def render_route_table(routes):
    lines = [
        "| Method | Path | Summary |",
        "| --- | --- | --- |",
    ]
    for item in routes:
        lines.append(f"| {item['method']} | `{item['path']}` | {item['summary']} |")
    return "\n".join(lines)


def generate_readme() -> str:
    source = read_text(MAIN_FILE)
    meta = extract_fastapi_metadata(source)
    routes = meta["routes"]

    route_table = render_route_table(routes)

    content = dedent(
        f"""
        # {PROJECT['name']} — {PROJECT['tagline']}

        {PROJECT['summary']}

        <p align="center">
          <img alt="Aeglis brand" src="https://img.shields.io/badge/Aeglis-Captcha%20Security-blue?style=for-the-badge" />
          <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.110+-green?style=for-the-badge" />
          <img alt="Redis" src="https://img.shields.io/badge/Redis-Session%20Store-red?style=for-the-badge" />
          <img alt="Supabase" src="https://img.shields.io/badge/Supabase-Postgres%20Auth-orange?style=for-the-badge" />
        </p>

        ## Overview

        Aeglis protects customer-facing web applications from bots, scripted traffic, and abuse patterns using a layered verification flow:

        - adaptive CAPTCHA challenge generation
        - Proof-of-Work CPU tax to slow bots
        - WebGL and DOM trap validation
        - behavioral telemetry and mouse entropy scoring
        - puzzle fallback for borderline traffic
        - API-based integration for site owners and dashboarding for admins

        This backend exposes a FastAPI service designed for sites that need a fraud-resistant challenge flow without a heavy frontend dependency. The app is mounted under `/api/v1/captcha` and the interactive OpenAPI docs are available at `/docs`.

        ## Product Highlights

        - Multi-step challenge engine with challenge, verify, and puzzle phases
        - Redis-backed ephemeral challenge state with short expiry windows
        - Supabase-powered customer keys, analytics, billing metadata, and authentication
        - Rate-limited endpoints with backend telemetry and abuse monitoring
        - Dashboard-ready analytics endpoints for blocked requests and pass rates
        - Flexible product-ready core for captcha and bot-protection workflows

        ## Architecture

        ```text
        Browser / Frontend
            │
            ▼
        Aeglis API (FastAPI)
            ├─ Redis: ephemeral session + token storage
            ├─ Supabase: auth + site keys + analytics + account metadata
            └─ Challenge engine: PoW + DOM + WebGL + behavior analysis
        ```

        ## Core Verification Flow

        1. A frontend calls `POST /api/v1/captcha/challenge` to obtain a session and challenge payload.
        2. The browser solves the Proof-of-Work requirement and sends telemetry back to `POST /api/v1/captcha/verify`.
        3. The backend evaluates the session using WebGL, mouse entropy, time, DOM trap, and IP heuristics.
        4. If confidence is low, the request is escalated to `POST /api/v1/captcha/puzzle-solve`.
        5. A signed token is returned to the client only when the bot-risk score passes the configured threshold.

        ## Tech Stack

        - Python 3.10+
        - FastAPI
        - Uvicorn
        - Redis
        - Supabase
        - Pydantic models for validation
        - SlowAPI rate limiting
        - APScheduler for maintenance jobs

        ## Project Structure

        ```text
        .
        ├── main.py                  # FastAPI app and API routes
        ├── captcha_engine.py        # CAPTCHA challenge logic and verification engine
        ├── redis_client.py         # Redis connection bootstrap
        ├── requirements.txt        # Python dependencies
        ├── readme.py               # Generates this README.md
        ├── utils/
        │   └── supabase_db.py      # Supabase client bootstrap and auth helper
        └── README.md               # Product documentation
        ```

        ## Quick Start

        ### 1) Install dependencies

        ```bash
        python -m venv .venv
        . .venv/bin/activate  # Windows: .venv\\Scripts\\activate
        pip install -r requirements.txt
        ```

        ### 2) Configure environment variables

        Create a `.env` file in the project root using the following format:

        ```env
        {make_env_block()}
        ```

        ### 3) Run the API server

        ```bash
        python main.py
        ```

        The server starts on `http://0.0.0.0:8001` and the Swagger UI is available at:

        ```text
        http://localhost:8001/docs
        ```

        ## API Overview

        The app exposes a versioned API namespace at `/api/v1/captcha`.

        {route_table}

        ## Example Requests

        ### Challenge request

        ```bash
        curl -X POST http://localhost:8001/api/v1/captcha/challenge \
          -H "Content-Type: application/json" \
          -d '{{"site_key":"pk_live_example"}}'
        ```

        ### Verification request

        ```bash
        curl -X POST http://localhost:8001/api/v1/captcha/verify \
          -H "Content-Type: application/json" \
          -d '{{
            "session_id": "sess_123",
            "pow_nonce": 6137,
            "webgl_hash": "renderer-example",
            "clicked_class": "example-button",
            "interaction_time_ms": 280,
            "site_key": "pk_live_example",
            "mouse_trail": [[10,20,12.3],[12,22,12.8],[20,35,13.5]]
          }}'
        ```

        ## Dashboard and Account APIs

        In addition to the challenge engine, Aeglis provides routes for key management, analytics, billing, and profile access:

        - `GET /api/v1/captcha/keys` — fetch configured site keys
        - `POST /api/v1/captcha/keys/generate` — generate public/secret pair
        - `PUT /api/v1/captcha/keys/regenerate` — rotate keys
        - `GET /api/v1/captcha/analytics/overview` — fetch blocked/pass statistics
        - `GET /api/v1/captcha/analytics/logs` — fetch request logs
        - `GET /api/v1/captcha/billing/usage` — current billing usage data
        - `POST /api/v1/captcha/billing/checkout` — create checkout URL
        - `POST /api/v1/captcha/profile/me` — fetch authenticated profile

        ## Security Model

        Aeglis combines multiple detection layers instead of relying on a single signal:

        - bot-resistant Proof of Work with a variable difficulty target
        - WebGL/renderer blocking against known suspicious signatures
        - DOM trap detection for fake click paths
        - mouse movement entropy analysis to identify scripted input
        - timing heuristics for unrealistic interaction speed
        - IP reputation heuristics for datacenter or cloud-origin traffic

        These checks are designed to reduce fraud while keeping user friction low for legitimate visitors. The backend is also rate-limited to protect public endpoints from abuse.

        ## Production Notes

        - Expose the service behind TLS and a reverse proxy such as Nginx or Caddy.
        - Set proper secret management for all Supabase credentials.
        - Use Redis in a managed environment for production resilience.
        - Monitor failed challenge rates, blocked requests, and API latency in analytics.
        - Extend the bot signature tables and heuristics as your traffic profile evolves.

        ## License

        This project is intended for internal product usage and deployment. Add your preferred project license before production release.

        ## Contributing

        1. Fork the repository.
        2. Create a feature branch.
        3. Add or update tests and documentation.
        4. Validate the service locally using the FastAPI docs and sample requests.
        5. Open a pull request with a clear summary of the change.

        ---

        Built for real-world bot protection and trust enforcement.
        """
    )

    cleaned_lines = []
    for line in content.splitlines():
        if line.startswith("        "):
            cleaned_lines.append(line[8:])
        else:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip() + "\n"


def main() -> None:
    readme = generate_readme()
    OUTPUT_FILE.write_text(readme, encoding="utf-8")
    print(f"README generated successfully at {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
