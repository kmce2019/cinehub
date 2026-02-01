"""Simple recommendation engine for CineHub.

The recommender consumes data from Jellyfin and TMDB to produce lists of
items to suggest to the user. Currently, it uses trending titles from
TMDB and filters out items already present in the local library. In
future iterations, this module could incorporate user ratings and
watch history for personalized recommendations.
"""

from __future__ import annotations

from typing import List, Dict

from .jellyfin import JellyfinClient
from .tmdb import TMDBClient


class Recommender:
    def __init__(self, jellyfin: JellyfinClient, tmdb: TMDBClient) -> None:
        self.jellyfin = jellyfin
        self.tmdb = tmdb

    def recommend_download(self, limit: int = 24) -> List[Dict]:
        """Suggest titles not currently in the library.

        Pulls trending titles from TMDB and filters out any that are
        already present in the local Jellyfin library. Only the first
        ``limit`` items are returned.
        """
        candidates = self.tmdb.get_trending(limit=100)
        suggestions: List[Dict] = []
        for item in candidates:
            media_type = item.get("media_type") or ("tv" if item.get("name") else "movie")
            tmdb_id = item.get("id")
            if tmdb_id is None:
                continue
            if self.jellyfin.is_in_library(tmdb_id=tmdb_id, media_type=media_type):
                continue
            suggestions.append(item)
            if len(suggestions) >= limit:
                break
        return suggestions