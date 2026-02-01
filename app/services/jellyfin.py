"""Jellyfin API client.

This module defines a simple client for the Jellyfin API. It supports
retrieving recently added items, continue watching items, fetching
individual item details, checking if a TMDB item exists in the local
library, enumerating active sessions and sending play commands, and
constructing stream URLs.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests


class JellyfinClient:
    def __init__(self, lan_url: str, wan_url: str, api_key: str, user_id: str) -> None:
        self.lan_url = lan_url.rstrip("/")
        self.wan_url = wan_url.rstrip("/")
        self.api_key = api_key
        self.user_id = user_id
        self.default_headers = {
            "X-Emby-Token": api_key,
            "accept": "application/json",
        }

    @classmethod
    def from_env(cls) -> "JellyfinClient":
        return cls(
            lan_url=os.environ.get("JELLYFIN_LAN_URL", "http://localhost:8096"),
            wan_url=os.environ.get("JELLYFIN_WAN_URL", "http://localhost:8096"),
            api_key=os.environ.get("JELLYFIN_API_KEY", ""),
            user_id=os.environ.get("JELLYFIN_USER_ID", ""),
        )

    def _base(self) -> str:
        """Choose the LAN base URL if reachable, else fallback to WAN.

        A simple HEAD request is used with a short timeout. If the LAN
        server responds, it will be used for subsequent API calls.
        """
        try:
            requests.head(self.lan_url, timeout=0.5)
            return self.lan_url
        except Exception:
            return self.wan_url

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self._base()}{path}"
        resp = requests.get(url, headers=self.default_headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_recently_added(self, limit: int = 24) -> List[Dict[str, Any]]:
        path = f"/Users/{self.user_id}/Items/Latest"
        return self._get(path, params={"Limit": limit})

    def get_continue_watching(self, limit: int = 24) -> List[Dict[str, Any]]:
        path = f"/Users/{self.user_id}/Items/Resume"
        data = self._get(path, params={"Limit": limit})
        return data.get("Items", data)  # older versions return list directly

    def get_item(self, item_id: str) -> Dict[str, Any]:
        path = f"/Users/{self.user_id}/Items/{item_id}"
        return self._get(path)

    def is_in_library(self, tmdb_id: int, media_type: str) -> bool:
        # Search library by provider ID (tmdb) to see if item exists
        path = "/Items"
        data = self._get(path, params={"AnyProviderIdEquals": f"tmdb.{tmdb_id}"})
        total = data.get("TotalRecordCount")
        return bool(total)

    def stream_url(self, item_id: str) -> str:
        # Construct direct stream URL with API key
        return f"{self._base()}/Videos/{item_id}/stream?api_key={self.api_key}"

    # Session management for sending items to devices (e.g. Apple TV)
    def list_sessions(self) -> List[Dict[str, Any]]:
        return self._get("/Sessions")

    def play_item(self, session_id: str, item_id: str) -> Dict[str, Any]:
        # Send play command to the given session
        url = f"{self._base()}/Sessions/{session_id}/Playing"  # Post body includes item id
        payload = {
            "ItemIds": [item_id],
            "PlayCommand": "PlayNow",
        }
        resp = requests.post(url, headers=self.default_headers, json=payload, timeout=10)
        return {"status_code": resp.status_code, "response": resp.text}