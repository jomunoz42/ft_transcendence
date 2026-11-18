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
        profile = me.raise_for_status().json()
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise Ft42Error(str(error)) from error
    if not _looks_like_a_profile(profile):
        raise Ft42Error("unexpected /v2/me profile shape")
    return profile


def _looks_like_a_profile(profile) -> bool:
    """True when the profile has what login_with_42 relies on: an int `id`, a usable `login`, a string or absent `email`."""
    return (
        isinstance(profile, dict)
        and type(profile.get("id")) is int
        and isinstance(profile.get("login"), str)
        and profile["login"].strip() != ""
        and "\x00" not in profile["login"]
        and isinstance(profile.get("email"), (str, type(None)))
    )
