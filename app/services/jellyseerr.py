"""Jellyseerr API client.

Provides minimal functionality to submit media requests. Jellyseerr is a fork
of Overseerr and exposes a similar API. This client uses the API key
configured in the environment.
"""

from __future__ import annotations

import os
from typing import Any, Dict

import requests


class JellyseerrClient:
    def __init__(self, base_url: str, api_key: str, user_id: str | None = None) -> None:
        self.base = base_url.rstrip("/")
        self.api_key = api_key
        self.user_id = user_id
        self.default_headers = {
            "X-Api-Key": api_key,
            "accept": "application/json",
        }

    @classmethod
    def from_env(cls) -> "JellyseerrClient":
        return cls(
            base_url=os.environ.get("JELLYSEERR_URL", "http://localhost:5055"),
            api_key=os.environ.get("JELLYSEERR_API_KEY", ""),
            user_id=os.environ.get("JELLYSEERR_USER_ID", None),
        )

    def request(self, media_type: str, tmdb_id: int) -> Dict[str, Any]:
        """Submit a media request to Jellyseerr.

        :param media_type: Either "movie" or "tv".
        :param tmdb_id: The TMDB ID of the title to request.
        :returns: Dictionary with success status and any errors.
        """
        url = f"{self.base}/api/v1/request"
        payload: Dict[str, Any] = {"mediaType": media_type, "mediaId": tmdb_id}
        # Optionally include user id if configured (some instances support it)
        if self.user_id:
            payload["userId"] = self.user_id
        resp = requests.post(url, headers=self.default_headers, json=payload, timeout=15)
        if resp.ok:
            return {"ok": True, "data": resp.json()}
        return {"ok": False, "status": resp.status_code, "error": resp.text}