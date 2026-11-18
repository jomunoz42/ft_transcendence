"""The 42 API calls of the OAuth login: trade the callback's code for a token, then read the user's profile."""

import os

import httpx

TOKEN_URL = "https://api.intra.42.fr/oauth/token"
ME_URL = "https://api.intra.42.fr/v2/me"


class Ft42Error(Exception):
    """42 refused the code or could not be reached."""


def profile_from_code(code: str, http: httpx.Client) -> dict:
    """The /v2/me profile of the 42 user who granted this code. Raises Ft42Error on any failure."""
    try:
        token = http.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": os.environ["FT42_CLIENT_ID"],
                "client_secret": os.environ["FT42_CLIENT_SECRET"],
                "code": code,
                "redirect_uri": os.environ["FT42_REDIRECT_URI"],
            },
        ).raise_for_status()
        me = http.get(ME_URL, headers={"Authorization": f"Bearer {token.json()['access_token']}"})
        return me.raise_for_status().json()
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise Ft42Error(str(error)) from error
