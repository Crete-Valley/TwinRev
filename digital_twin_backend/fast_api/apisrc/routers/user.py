import os

import requests
from fastapi import APIRouter, HTTPException

from ..config import client_key
from ..schemas import SignInRequest


router = APIRouter()


@router.post("/user/signin", tags=["User"])
def user_signin(credentials: SignInRequest):
    # OpenID Connect token endpoint of the identity provider (e.g. Keycloak).
    # Supplied at deploy time; sign-in is disabled when unset.
    token_url = os.getenv("KEYCLOAK_TOKEN_URL")
    if not token_url:
        raise HTTPException(
            status_code=503,
            detail="Sign-in is not configured (KEYCLOAK_TOKEN_URL is unset).",
        )

    payload = {
        "client_id": os.getenv("KEYCLOAK_CLIENT_ID", "digital_twin"),
        "client_secret": client_key,
        "username": credentials.username,
        "password": credentials.password,
        "grant_type": "password",
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        response = requests.post(token_url, data=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError:
        raise HTTPException(status_code=response.status_code, detail=response.text)
