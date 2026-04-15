#!/usr/bin/env python3
"""HubSpot OAuth token management.

Handles token refresh and provides a valid access token for API calls.

Requires environment variables:
    HUBSPOT_CLIENT_ID      — OAuth app client ID
    HUBSPOT_CLIENT_SECRET  — OAuth app client secret

Tokens (access + refresh) are stored per-user in ~/.claude/hubspot_tokens.json.

Usage:
    # Print current access token (refreshes if needed)
    python3 auth.py

    # Force refresh
    python3 auth.py --refresh

    # Run initial OAuth setup (interactive)
    python3 auth.py --setup
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse

TOKENS_FILE = os.path.expanduser("~/.claude/hubspot_tokens.json")
TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"


def get_client_credentials():
    client_id = os.environ.get("HUBSPOT_CLIENT_ID")
    client_secret = os.environ.get("HUBSPOT_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Error: HUBSPOT_CLIENT_ID and HUBSPOT_CLIENT_SECRET environment variables are required.", file=sys.stderr)
        print("See SKILL.md for setup instructions.", file=sys.stderr)
        sys.exit(1)
    return client_id, client_secret


def load_tokens():
    if not os.path.exists(TOKENS_FILE):
        return {}
    with open(TOKENS_FILE) as f:
        return json.load(f)


def save_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)


def refresh_token(tokens):
    client_id, client_secret = get_client_credentials()
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": tokens["refresh_token"],
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded",
    })

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    tokens["access_token"] = result["access_token"]
    tokens["refresh_token"] = result["refresh_token"]
    tokens["expires_in"] = result["expires_in"]
    tokens["last_refresh"] = int(time.time())
    save_tokens(tokens)
    return tokens


def exchange_code(code, code_verifier, redirect_uri="http://localhost:3000/oauth/callback"):
    """Exchange an authorization code for access + refresh tokens."""
    client_id, client_secret = get_client_credentials()
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": code,
        "code_verifier": code_verifier,
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded",
    })

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    tokens = {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "expires_in": result["expires_in"],
        "last_refresh": int(time.time()),
    }
    save_tokens(tokens)
    print(f"Authenticated successfully. Hub ID: {result.get('hub_id')}", file=sys.stderr)
    print(f"Scopes: {len(result.get('scopes', []))} granted", file=sys.stderr)
    print(f"Tokens saved to {TOKENS_FILE}", file=sys.stderr)
    return tokens


def setup():
    """Interactive OAuth setup flow."""
    import hashlib
    import base64
    import secrets

    client_id, _ = get_client_credentials()

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": "http://localhost:3000/oauth/callback",
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })

    auth_url = f"https://app.hubspot.com/oauth/authorize?{params}"

    print("\n=== HubSpot OAuth Setup ===\n")
    print("1. Open this URL in your browser:\n")
    print(f"   {auth_url}\n")
    print("2. Grant permissions when prompted.")
    print("3. You'll be redirected to localhost:3000. Copy the 'code' parameter from the URL.")
    print("   (The page will fail to load — that's expected. Just copy the code from the URL bar.)\n")

    code = input("Paste the authorization code here: ").strip()
    if not code:
        print("No code provided. Aborting.", file=sys.stderr)
        sys.exit(1)

    exchange_code(code, code_verifier)


def get_token(force_refresh=False):
    tokens = load_tokens()
    if not tokens.get("refresh_token"):
        print("Error: No tokens found. Run 'python3 auth.py --setup' to authenticate.", file=sys.stderr)
        sys.exit(1)

    last_refresh = tokens.get("last_refresh", 0)
    expires_in = tokens.get("expires_in", 1800)

    # Refresh if token is older than 25 minutes (5 min buffer before 30 min expiry)
    if force_refresh or (time.time() - last_refresh) > (expires_in - 300):
        tokens = refresh_token(tokens)
        print("Token refreshed", file=sys.stderr)

    return tokens["access_token"]


if __name__ == "__main__":
    if "--setup" in sys.argv:
        setup()
    else:
        force = "--refresh" in sys.argv
        token = get_token(force_refresh=force)
        print(token)
