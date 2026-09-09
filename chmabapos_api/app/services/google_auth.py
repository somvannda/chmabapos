from __future__ import annotations

from typing import Any

import httpx
import jwt

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

_jwks_client = jwt.PyJWKClient(GOOGLE_CERTS_URL, cache_keys=True)


def verify_google_id_token(id_token: str, client_id: str) -> dict[str, Any]:
    """Verify a Google Sign-In ID token and return its claims.

    Raises jwt.PyJWTError (e.g. InvalidTokenError, ExpiredSignatureError) when the
    token is not signed by Google, has expired, or was issued for another client.
    """
    signing_key = _jwks_client.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=GOOGLE_ISSUERS,
        options={"verify_exp": True, "require": ["sub", "email"]},
    )
    return claims


async def exchange_authorization_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange an OAuth authorization code for Google tokens (server side).

    Raises httpx.HTTPError on a non-2xx response from Google.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        data = response.json()
    if not data.get("id_token"):
        raise ValueError("Google did not return an id_token")
    return data

