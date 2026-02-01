"""Provider resolution and device playback helpers.

This module contains helper functions to construct deep links or search
queries for third-party streaming providers (e.g. Netflix, Max, Discovery+,
YouTube, YouTube TV) and to send playback commands to devices via
Jellyfin sessions.

The "resolve_provider_link" function attempts to build a URL that opens
the given provider with the title ready to play or search results
pre-populated. Note that auto-play may not be possible on many
providers; landing on the title page or search results is the best we
can offer. For full-length YouTube playback, an API key can be
provided via environment variable and will be used to find the most
relevant video.
"""

from __future__ import annotations

import os
import urllib.parse
from typing import Any, Dict, List, Tuple

import requests

from .jellyfin import JellyfinClient


def resolve_provider_link(title: str, media_type: str, tmdb_id: int, year: int | None = None, provider: str = "netflix") -> str:
    """Return a URL that best opens the provider app or search for the title.

    :param title: The title of the movie or show.
    :param media_type: "movie" or "tv".
    :param tmdb_id: The TMDB ID of the title.
    :param year: Optional release year to improve search precision.
    :param provider: One of "netflix", "max", "discovery", "youtube", "youtube_tv".
    :returns: A URL string to open in the provider app or web.
    """
    normalized = title
    if year:
        normalized = f"{title} ({year})"

    # Provider-specific URL patterns. Many providers do not have public deep
    # links; the patterns below reflect best-effort behavior.
    if provider == "netflix":
        # Netflix sometimes uses title IDs (internal). Without that, we fall
        # back to a search URL. The general format for opening a search on
        # Netflix is: https://www.netflix.com/search?q=<query>
        query = urllib.parse.quote_plus(normalized)
        return f"https://www.netflix.com/search?q={query}"
    if provider == "max":
        # Max (formerly HBO Max) search page
        query = urllib.parse.quote_plus(normalized)
        return f"https://play.max.com/search?q={query}"
    if provider == "discovery":
        # Discovery+ search page
        query = urllib.parse.quote_plus(normalized)
        return f"https://discoveryplus.com/search?q={query}"
    if provider == "youtube":
        # Attempt to find a full-length video via YouTube Data API if key provided
        api_key = os.environ.get("YOUTUBE_DATA_API_KEY")
        if api_key:
            video_id = _find_youtube_video_id(normalized, api_key)
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"
        # Fall back to search results
        query = urllib.parse.quote_plus(f"{normalized} full movie")
        return f"https://www.youtube.com/results?search_query={query}"
    if provider == "youtube_tv":
        # YouTube TV does not support deep links. Use search to land on results.
        query = urllib.parse.quote_plus(normalized)
        return f"https://tv.youtube.com/search?q={query}"
    # Default fallback: Google search
    query = urllib.parse.quote_plus(normalized)
    return f"https://www.google.com/search?q={query}"


def _find_youtube_video_id(query: str, api_key: str) -> str | None:
    """Try to find the first YouTube video ID matching the query using the Data API.

    This function performs a simple search for videos matching the query
    and returns the first videoId from the results. It returns None if
    the API request fails or no results are found.
    """
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "maxResults": 5,
        "q": query,
        "type": "video",
        "key": api_key,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            return None
        return items[0]["id"]["videoId"]
    except Exception:
        return None


def list_playback_devices(jellyfin: JellyfinClient) -> List[Dict[str, Any]]:
    """Return a list of active sessions that may accept playback commands.

    Each session dictionary includes keys like "Id", "DeviceName", "Client",
    and a boolean "Controllable" based on whether the session is likely
    controllable.
    """
    sessions = jellyfin.list_sessions()
    devices: List[Dict[str, Any]] = []
    for s in sessions:
        device_name = s.get("DeviceName") or s.get("DeviceId") or "Unknown"
        client = s.get("Client") or s.get("DeviceType") or ""
        controllable = bool(s.get("SupportsRemoteControl"))
        devices.append(
            {
                "id": s.get("Id"),
                "device_name": device_name,
                "client": client,
                "controllable": controllable,
            }
        )
    return devices


def send_to_device(jellyfin: JellyfinClient, session_id: str, item_id: str) -> Dict[str, Any]:
    """Send the specified item to play on the given Jellyfin session.

    If the session supports remote control, this will attempt to start
    playback immediately. The response includes the HTTP status code
    and response text from Jellyfin.
    """
    return jellyfin.play_item(session_id=session_id, item_id=item_id)