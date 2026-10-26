"""dlt source for the Steam Store `appdetails` and review endpoints (no API key needed)."""

import json
import logging
import time
from collections.abc import Iterator
from datetime import UTC, datetime

import dlt
import requests

from steam_data_platform.settings import (
    REQUEST_PAUSE_SECONDS,
    STORE_COUNTRY,
    STORE_LANGUAGE,
)

logger = logging.getLogger(__name__)

APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
REQUEST_TIMEOUT_SECONDS = 10
MAX_ATTEMPTS = 3
PROGRESS_EVERY = 10  # log a progress line every 10 games
BACKOFF_SECONDS = 30  # waits 30s after attempt 1, 60s after attempt 2
REVIEWS_URL = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"


class SteamRequestError(RuntimeError):
    """One game could not be fetched after all attempts; we skip that game."""


class SteamRateLimitError(SteamRequestError):
    """Steam kept answering 429 (too many requests); the whole run must stop."""


def fetch_app_details(appid: int) -> dict | None:
    """Call appdetails for ONE game (Steam rejects several full requests at once).

    Returns the game's `data` dict, or None if Steam says success is false.
    Retries timeouts, 5xx and 429 with a growing pause. Raises
    SteamRateLimitError if the last attempt was still a 429, and
    SteamRequestError for other problems that outlast all attempts.
    """
    params = {"appids": appid, "cc": STORE_COUNTRY, "l": STORE_LANGUAGE}
    problem = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                APPDETAILS_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS
            )
        except (requests.Timeout, requests.ConnectionError) as error:
            problem = type(error).__name__
        else:
            if response.status_code == 429 or response.status_code >= 500:
                problem = f"HTTP {response.status_code}"
            else:
                response.raise_for_status()  # any other 4xx is a bug on our side
                # A 200 can still mean "not found"; the body is keyed by the
                # appid as a STRING, and can be `null`.
                entry = (response.json() or {}).get(str(appid)) or {}
                return entry.get("data") if entry.get("success") else None

        if attempt < MAX_ATTEMPTS:
            wait = BACKOFF_SECONDS * attempt
            logger.warning(
                "appid %s: %s (attempt %s/%s), waiting %ss",
                appid,
                problem,
                attempt,
                MAX_ATTEMPTS,
                wait,
            )
            time.sleep(wait)

    message = f"appid {appid}: {problem} after {MAX_ATTEMPTS} attempts"
    if problem == "HTTP 429":
        raise SteamRateLimitError(message)
    raise SteamRequestError(message)


def get_with_retry(url: str, params: dict, label: str) -> requests.Response:
    """GET with a timeout; retries timeouts, 5xx and 429 with a growing pause.

    Raises SteamRateLimitError if the last attempt was still a 429, and
    SteamRequestError for other problems that outlast all attempts.
    """
    problem = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        except (requests.Timeout, requests.ConnectionError) as error:
            problem = type(error).__name__
        else:
            if response.status_code == 429 or response.status_code >= 500:
                problem = f"HTTP {response.status_code}"
            else:
                response.raise_for_status()  # any other 4xx is a bug on our side
                return response

        if attempt < MAX_ATTEMPTS:
            wait = BACKOFF_SECONDS * attempt
            logger.warning(
                "%s: %s (attempt %s/%s), waiting %ss",
                label,
                problem,
                attempt,
                MAX_ATTEMPTS,
                wait,
            )
            time.sleep(wait)

    message = f"{label}: {problem} after {MAX_ATTEMPTS} attempts"
    if problem == "HTTP 429":
        raise SteamRateLimitError(message)
    raise SteamRequestError(message)


def fetch_review_summary(appid: int) -> dict | None:
    """Call GetAppReviews for ONE game and return its `query_summary` block.

    We ask for a single review per page because we only want the totals.
    Returns None if the answer has no usable summary.
    """
    options = {"appid": appid, "num_per_page": 1, "language": "all"}
    response = get_with_retry(
        REVIEWS_URL, {"input_json": json.dumps(options)}, f"appid {appid}"
    )
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    summary = (body.get("response") or {}).get("query_summary")
    if not isinstance(summary, dict) or "total_reviews" not in summary:
        return None
    return summary


def build_game_row(data: dict, collected_at: datetime) -> dict:
    """Pick the fields we keep and flatten them into one row.

    Prices stay as Steam sends them: whole numbers in minor units (969 = 9,69 EUR).
    Free games have no price_overview, so every price field may be None.
    """
    price = data.get("price_overview", {})
    release = data.get("release_date", {})
    platforms = data.get("platforms", {})

    return {
        "steam_appid": data["steam_appid"],
        "collected_at": collected_at,
        "name": data.get("name"),
        "type": data.get("type"),
        "is_free": data.get("is_free"),
        "required_age": data.get("required_age"),
        "short_description": data.get("short_description"),
        "website": data.get("website"),
        "release_date_text": release.get("date"),  # plain text, e.g. "18 Apr, 2011"
        "coming_soon": release.get("coming_soon"),
        "price_currency": price.get("currency"),
        "price_initial": price.get("initial"),
        "price_final": price.get("final"),
        "discount_percent": price.get("discount_percent"),
        "metacritic_score": data.get("metacritic", {}).get("score"),
        "recommendations_total": data.get("recommendations", {}).get("total"),
        "platform_windows": platforms.get("windows"),
        "platform_mac": platforms.get("mac"),
        "platform_linux": platforms.get("linux"),
        # Lists of text, stored inside the row (see `columns` on the resource).
        "developers": data.get("developers", []),
        "publishers": data.get("publishers", []),
        "genres": [g["description"] for g in data.get("genres", [])],
        "categories": [c["description"] for c in data.get("categories", [])],
    }


def build_review_row(appid: int, summary: dict, collected_at: datetime) -> dict:
    """Keep the review totals as Steam sends them (counts, score 0-9, label)."""
    return {
        "steam_appid": appid,
        "collected_at": collected_at,
        "review_score": summary.get("review_score"),
        "review_score_desc": summary.get("review_score_desc"),
        "total_positive": summary.get("total_positive"),
        "total_negative": summary.get("total_negative"),
        "total_reviews": summary.get("total_reviews"),
    }


@dlt.resource(
    name="games",
    # append = keep every collection as a new row, so price changes build a history.
    write_disposition="append",
    columns={
        # Set the type ourselves instead of letting dlt guess it.
        "collected_at": {"data_type": "timestamp"},
        # Store these lists as JSON in one column instead of dlt making child tables.
        "developers": {"data_type": "json"},
        "publishers": {"data_type": "json"},
        "genres": {"data_type": "json"},
        "categories": {"data_type": "json"},
    },
)
def games(appids: list[int]) -> Iterator[dict]:
    """One row per game per collection run.

    A game that cannot be fetched is logged and skipped. If Steam keeps
    answering 429 we stop the whole run instead of hammering it.
    """
    collected_at = datetime.now(UTC)
    fetched = skipped = failed = 0

    for position, appid in enumerate(appids):
        if position > 0:
            time.sleep(REQUEST_PAUSE_SECONDS)
        try:
            data = fetch_app_details(appid)
        except SteamRateLimitError:
            logger.error("Steam rate limit hit at appid %s; stopping the run", appid)
            raise
        except (SteamRequestError, requests.RequestException) as error:
            failed += 1
            logger.error("appid %s: failed, skipping (%s)", appid, error)
            continue

        if data is None:
            skipped += 1
            logger.warning("appid %s: Steam returned success=false, skipping", appid)
            continue

        fetched += 1
        yield build_game_row(data, collected_at)

    logger.info(
        "games: %s fetched, %s skipped (success=false), %s failed, of %s requested",
        fetched,
        skipped,
        failed,
        len(appids),
    )


@dlt.resource(
    name="review_summary",
    # append = one new row per game per run, so sentiment builds a history.
    write_disposition="append",
    columns={"collected_at": {"data_type": "timestamp"}},
)
def review_summary(appids: list[int]) -> Iterator[dict]:
    """One row per game per collection run with the review totals.

    A game that cannot be fetched is logged and skipped. If Steam keeps
    answering 429 we stop the whole run instead of hammering it.
    """
    collected_at = datetime.now(UTC)
    fetched = skipped = failed = 0

    for position, appid in enumerate(appids):
        if position > 0:
            if position % PROGRESS_EVERY == 0:
                logger.info(
                    "review_summary: %s of %s games done", position, len(appids)
                )
            time.sleep(REQUEST_PAUSE_SECONDS)
        try:
            summary = fetch_review_summary(appid)
        except SteamRateLimitError:
            logger.error("Steam rate limit hit at appid %s; stopping the run", appid)
            raise
        except (SteamRequestError, requests.RequestException) as error:
            failed += 1
            logger.error("appid %s: failed, skipping (%s)", appid, error)
            continue

        if summary is None:
            skipped += 1
            logger.warning("appid %s: no review summary, skipping", appid)
            continue

        fetched += 1
        yield build_review_row(appid, summary, collected_at)

    logger.info(
        "review_summary: %s fetched, %s skipped (no summary), %s failed, of %s requested",
        fetched,
        skipped,
        failed,
        len(appids),
    )


@dlt.source(name="steam")
def steam_source(appids: list[int]):
    """Groups the Steam resources so they load together in one pipeline."""
    return games(appids), review_summary(appids)
