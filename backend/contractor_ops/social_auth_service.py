"""
Social authentication service — Google + Apple Sign-In.
Phone number is ALWAYS mandatory. Social login is a secondary auth method.
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta

import jwt as pyjwt
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from config import (
    GOOGLE_CLIENT_ID_WEB,
    GOOGLE_CLIENT_ID_IOS,
    GOOGLE_CLIENT_ID_ANDROID,
    APPLE_BUNDLE_ID,
)

logger = logging.getLogger(__name__)

SOCIAL_SESSION_TTL = timedelta(minutes=10)


async def verify_google_token(id_token_str: str) -> dict:
    """
    Verify Google ID token.
    Returns {sub, email, name, picture}.
    Accepts tokens from web, iOS, and Android client IDs.
    Raises ValueError on invalid token.
    """
    try:
        client_ids = [cid for cid in [GOOGLE_CLIENT_ID_WEB, GOOGLE_CLIENT_ID_IOS, GOOGLE_CLIENT_ID_ANDROID] if cid]
        if not client_ids:
            logger.error("Google client IDs not configured")
            raise ValueError("אימות Google נכשל — שירות לא מוגדר")

        for client_id in client_ids:
            try:
                idinfo = google_id_token.verify_oauth2_token(
                    id_token_str,
                    google_requests.Request(),
                    client_id
                )
                return {
                    "sub": idinfo["sub"],
                    "email": idinfo.get("email", ""),
                    "name": idinfo.get("name", ""),
                    "picture": idinfo.get("picture", ""),
                }
            except ValueError:
                continue

        raise ValueError("אימות Google נכשל")
    except ValueError:
        raise
    except Exception as e:
        logger.warning("Google token verification failed: %s", e)
        raise ValueError("אימות Google נכשל") from e


async def verify_apple_token(id_token_str: str) -> dict:
    """
    Verify Apple ID token.
    Returns {sub, email}.
    Apple uses RS256 JWTs signed with keys from https://appleid.apple.com/auth/keys
    Note: Apple only sends email on FIRST sign-in. After that, only sub is guaranteed.
    Raises ValueError on invalid token.
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://appleid.apple.com/auth/keys")
            resp.raise_for_status()
            apple_keys = resp.json()

        header = pyjwt.get_unverified_header(id_token_str)
        kid = header.get("kid")

        key_data = None
        for key in apple_keys.get("keys", []):
            if key["kid"] == kid:
                key_data = key
                break
        if not key_data:
            logger.warning("Apple signing key kid=%s not found in JWKS", kid)
            raise ValueError("אימות Apple נכשל")

        from jwt.algorithms import RSAAlgorithm
        public_key = RSAAlgorithm.from_jwk(key_data)

        decoded = pyjwt.decode(
            id_token_str,
            public_key,
            algorithms=["RS256"],
            audience=APPLE_BUNDLE_ID,
            issuer="https://appleid.apple.com",
        )

        return {
            "sub": decoded["sub"],
            "email": decoded.get("email", ""),
        }
    except ValueError:
        raise
    except Exception as e:
        logger.warning("Apple token verification failed: %s", e)
        raise ValueError("אימות Apple נכשל") from e


async def create_social_session(db, data: dict) -> str:
    """
    Create a temporary session for the social auth flow (linking or registration).
    Returns session_token (UUID). Stored in social_auth_sessions collection.
    Manual expiry check — ISO string dates, consistent with BrikOps patterns.
    """
    session_token = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await db.social_auth_sessions.insert_one({
        "id": session_token,
        "provider": data["provider"],
        "social_id": data["social_id"],
        "email": data.get("email", ""),
        "name": data.get("name", ""),
        "flow": data["flow"],
        "user_id": data.get("user_id"),
        "phone": data.get("phone"),
        "created_at": now.isoformat(),
        "expires_at": (now + SOCIAL_SESSION_TTL).isoformat(),
    })

    return session_token


async def get_social_session(db, session_token: str) -> dict | None:
    """Retrieve and validate a social auth session. Returns None if expired or not found."""
    session = await db.social_auth_sessions.find_one({"id": session_token}, {"_id": 0})
    if not session:
        return None

    now = datetime.now(timezone.utc).isoformat()
    if session["expires_at"] < now:
        await db.social_auth_sessions.delete_one({"id": session_token})
        return None

    return session


async def delete_social_session(db, session_token: str):
    """Delete a social auth session after successful use."""
    await db.social_auth_sessions.delete_one({"id": session_token})
