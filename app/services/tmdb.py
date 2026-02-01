"""TMDB API client.

This module exposes helper functions to query TheMovieDB (TMDB) API for
trending titles, title details, watch providers, and stream highlights.
It uses the v3 API with an API key. See https://developer.themoviedb.org
for API documentation.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import requests


class TMDBClient:
    def __init__(self, api_key: str, region: str = "US", language: str = "en-US") -> None:
        self.api_key = api_key
        self.region = region
        self.language = language
        self.base = "https://api.themoviedb.org/3"

    @classmethod
    def from_env(cls) -> "TMDBClient":
        return cls(
            api_key=os.environ.get("TMDB_API_KEY", ""),
            region=os.environ.get("TMDB_REGION", "US"),
            language=os.environ.get("TMDB_LANGUAGE", "en-US"),
        )

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        url = f"{self.base}{path}"
        params = params or {}
        params["api_key"] = self.api_key
        if self.language:
            params["language"] = self.language
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_trending(self, limit: int = 24) -> List[Dict[str, Any]]:
        data = self._get("/trending/all/week")
        return data.get("results", [])[:limit]

    def get_details(self, media_type: str, tmdb_id: int) -> Dict[str, Any]:
        path = f"/{media_type}/{tmdb_id}"
        return self._get(path)

    def get_watch_providers(self, media_type: str, tmdb_id: int) -> Dict[str, Any]:
        path = f"/{media_type}/{tmdb_id}/watch/providers"
        data = self._get(path)
        return data.get("results", {}).get(self.region, {})

    def get_streaming_highlights(self, limit: int = 24) -> List[Dict[str, Any]]:
        # For MVP reuse trending data; more sophisticated logic could be added later
        return self.get_trending(limit=limit)