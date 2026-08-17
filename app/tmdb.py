from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

import aiohttp

from app.config import get_settings

logger = logging.getLogger(__name__)

TMDB_API_BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


@dataclass(frozen=True)
class TMDBCandidate:
    tmdb_id: int
    title: str
    original_title: str | None
    release_date: str | None
    year: int | None
    overview: str | None
    poster_url: str | None
    backdrop_url: str | None
    rating: float | None
    popularity: float | None
    score: float


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    cleaned = "".join(c.lower() if c.isalnum() else " " for c in value)
    return " ".join(cleaned.split())


def _similarity(a: str, b: str) -> float:
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


class TMDBClient:
    def __init__(self) -> None:
        self.api_key = get_settings().tmdb_api_key.get_secret_value()

    async def search_movies(self, title: str, year: int | None = None, language: str | None = None) -> list[TMDBCandidate]:
        if not title.strip():
            return []

        params = {
            "api_key": self.api_key,
            "query": title.strip(),
            "include_adult": "false",
            "page": 1,
        }
        if year:
            params["year"] = year

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{TMDB_API_BASE}/search/movie", params=params) as response:
                if response.status == 401:
                    raise RuntimeError("TMDB API key is invalid")
                if response.status == 429:
                    raise RuntimeError("TMDB rate limit reached; try again shortly")
                if response.status >= 400:
                    body = await response.text()
                    logger.warning("TMDB search failed: HTTP %s: %s", response.status, body[:300])
                    raise RuntimeError(f"TMDB API returned HTTP {response.status}")
                data = await response.json()

        candidates: list[TMDBCandidate] = []
        for item in data.get("results", []):
            release_date = item.get("release_date") or None
            result_year = None
            if release_date and len(release_date) >= 4 and release_date[:4].isdigit():
                result_year = int(release_date[:4])

            title_score = max(
                _similarity(title, item.get("title")),
                _similarity(title, item.get("original_title")),
            )
            year_score = 0.0
            if year and result_year:
                diff = abs(year - result_year)
                year_score = 1.0 if diff == 0 else 0.65 if diff == 1 else 0.25 if diff <= 2 else 0.0
            elif not year:
                year_score = 0.5

            score = (title_score * 0.80) + (year_score * 0.20)
            candidates.append(
                TMDBCandidate(
                    tmdb_id=int(item["id"]),
                    title=item.get("title") or item.get("original_title") or "Unknown",
                    original_title=item.get("original_title"),
                    release_date=release_date,
                    year=result_year,
                    overview=item.get("overview"),
                    poster_url=f"{IMAGE_BASE}{item['poster_path']}" if item.get("poster_path") else None,
                    backdrop_url=f"{IMAGE_BASE}{item['backdrop_path']}" if item.get("backdrop_path") else None,
                    rating=float(item["vote_average"]) if item.get("vote_average") is not None else None,
                    popularity=float(item["popularity"]) if item.get("popularity") is not None else None,
                    score=score,
                )
            )

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:5]

    async def match_movie(self, title: str, year: int | None = None, language: str | None = None) -> tuple[TMDBCandidate | None, list[TMDBCandidate]]:
        candidates = await self.search_movies(title, year, language)
        if not candidates:
            return None, []
        best = candidates[0]
        second_score = candidates[1].score if len(candidates) > 1 else 0.0
        # Automatic matching requires both a strong title/year score and a useful margin.
        if best.score >= 0.86 and (best.score - second_score >= 0.06 or best.score >= 0.94):
            return best, candidates
        return None, candidates
