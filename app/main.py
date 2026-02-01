"""Main FastAPI application for CineHub.

This module defines the web interface routes, initialises service clients,
and renders templates for browsing and viewing media, rating items, and
requesting new downloads. It also supports sending items to other
devices via Jellyfin sessions when available.
"""

from __future__ import annotations

import os
from typing import Dict, List, Any

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .db import init_db, upsert_rating, get_rating
from .services.jellyfin import JellyfinClient
from .services.jellyseerr import JellyseerrClient
from .services.tmdb import TMDBClient
from .services.recommender import Recommender
from .services import provider


app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up template directory
templates = Jinja2Templates(directory="app/templates")

# Initialise database
init_db()

# Create clients from environment
jellyfin = JellyfinClient.from_env()
tmdb = TMDBClient.from_env()
jellyseerr = JellyseerrClient.from_env()
reco = Recommender(jellyfin=jellyfin, tmdb=tmdb)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Render the home page with a set of content rows."""
    # Jellyfin rows
    try:
        continue_watching = jellyfin.get_continue_watching()
    except Exception:
        continue_watching = []
    try:
        recently_added = jellyfin.get_recently_added()
    except Exception:
        recently_added = []
    # Recommendations
    try:
        recommended_download = reco.recommend_download(limit=12)
    except Exception:
        recommended_download = []
    try:
        trending = tmdb.get_trending(limit=12)
    except Exception:
        trending = []
    try:
        stream_picks = tmdb.get_streaming_highlights(limit=12)
    except Exception:
        stream_picks = []

    rows: List[Dict[str, Any]] = [
        {"title": "Continue Watching", "items": continue_watching, "kind": "jellyfin"},
        {"title": "Recently Added", "items": recently_added, "kind": "jellyfin"},
        {"title": "Recommended to Download", "items": recommended_download, "kind": "tmdb"},
        {"title": "Trending Now", "items": trending, "kind": "tmdb"},
        {"title": "Streaming Highlights", "items": stream_picks, "kind": "tmdb"},
    ]
    # Provide jellyfin base url for image tags in templates
    context = {
        "request": request,
        "rows": rows,
        "jellyfin_url": jellyfin._base(),
    }
    return templates.TemplateResponse("home.html", context)


@app.get("/title/{kind}/{item_id}", response_class=HTMLResponse)
async def title_detail(request: Request, kind: str, item_id: str, media_type: str | None = None) -> HTMLResponse:
    """Display details for a Jellyfin item or TMDB title."""
    if kind == "jellyfin":
        try:
            item = jellyfin.get_item(item_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Item not found")
        # List devices for sending playback
        devices = provider.list_playback_devices(jellyfin)
        play_url = jellyfin.stream_url(item_id)
        rating = get_rating("jellyfin", item_id)
        context = {
            "request": request,
            "kind": kind,
            "item": item,
            "devices": devices,
            "play_url": play_url,
            "rating": rating,
        }
        return templates.TemplateResponse("title.html", context)
    else:
        # TMDB
        if media_type is None:
            # Derive media_type from prefix
            media_type = "movie" if kind == "tmdb" else "movie"
        tmdb_id = int(item_id)
        try:
            item = tmdb.get_details(media_type=media_type, tmdb_id=tmdb_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Item not found")
        # Determine if the item is in library
        in_library = jellyfin.is_in_library(tmdb_id=tmdb_id, media_type=media_type)
        # Build provider links
        provider_names = ["netflix", "max", "discovery", "youtube", "youtube_tv"]
        # Attempt to include year for better search precision
        year = item.get("release_date") or item.get("first_air_date")
        year_int = None
        if year:
            try:
                year_int = int(year.split("-")[0])
            except Exception:
                year_int = None
        provider_links = {}
        for name in provider_names:
            url = provider.resolve_provider_link(
                title=item.get("title") or item.get("name"),
                media_type=media_type,
                tmdb_id=tmdb_id,
                year=year_int,
                provider=name,
            )
            provider_links[name] = url
        rating = get_rating("tmdb", f"{media_type}:{tmdb_id}")
        context = {
            "request": request,
            "kind": "tmdb",
            "item": item,
            "media_type": media_type,
            "in_library": in_library,
            "providers": provider_links,
            "provider_links": provider_links,
            "rating": rating,
        }
        return templates.TemplateResponse("title.html", context)


@app.post("/rate")
async def rate_item(source: str = Form(...), key: str = Form(...), stars: int = Form(...)) -> RedirectResponse:
    """Save a user rating for a particular item."""
    upsert_rating(source, key, int(stars))
    # Redirect back to home page
    return RedirectResponse(url="/", status_code=303)


@app.post("/request")
async def request_item(media_type: str = Form(...), tmdb_id: int = Form(...)) -> Dict[str, Any]:
    """Submit a download request via Jellyseerr."""
    result = jellyseerr.request(media_type=media_type, tmdb_id=tmdb_id)
    return result


@app.post("/send-to-device")
async def send_to_device(item_id: str = Form(...), session_id: str = Form(...)) -> RedirectResponse:
    """Send a library item to another device via Jellyfin sessions."""
    try:
        response = provider.send_to_device(jellyfin, session_id=session_id, item_id=item_id)
        # For now we ignore the response; could handle errors
    except Exception:
        pass
    # Redirect back to item page
    return RedirectResponse(url=f"/title/jellyfin/{item_id}", status_code=303)