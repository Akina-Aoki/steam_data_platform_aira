"""Gets Steam data and gives it to dlt, which loads it into Snowflake.

For each game in our list, one run does this:
    ask Steam  ->  shape the answer into one row  ->  hand the row to dlt

There are four Steam calls and five dlt resources (one table each). The recent
reviews use the same URL as the review totals, but ask two questions per game
(positive and negative). None of them needs an API key.
"""

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

# The Steam endpoints: game details, reviews (totals and recent), players, achievements.
APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
REQUEST_TIMEOUT_SECONDS = 10  # give up on one request after 10 seconds
MAX_ATTEMPTS = 3  # try each request at most 3 times
PROGRESS_EVERY = 10  # write a progress line to the log every 10 games
BACKOFF_SECONDS = 30  # wait 30 s after attempt 1, 60 s after attempt 2
REVIEWS_URL = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
PLAYERS_URL = (
    "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
)
ACHIEVEMENTS_URL = "https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/"
# Recent reviews: how many days to look back. Steam's review_type is a number.
# We tested it on Stellaris for all time: type 1 gave 119,757 and type 2 gave
# 19,965, which are the all-time positive and negative totals.
RECENT_DAYS = 30
REVIEW_TYPE_POSITIVE = 1
REVIEW_TYPE_NEGATIVE = 2


class SteamRequestError(RuntimeError):
    """A request for one game failed even after all attempts. We skip that game."""


class SteamRateLimitError(SteamRequestError):
    """Steam kept answering 429 ("too many requests"). We stop the whole run.

    It is a special kind of SteamRequestError.
    """


def fetch_app_details(appid: int) -> dict | None:
    """Ask Steam for the details of ONE game (name, price, genres, ...).

    Steam refuses several games in one request, so we send one request per game.
    Returns the game's `data` dict, or None if Steam says it has no such game.
    Retrying and errors are handled in `get_with_retry`.
    """
    # The question we send: which game, which country (for the price), which language.
    params = {"appids": appid, "cc": STORE_COUNTRY, "l": STORE_LANGUAGE}
    # The third value is only a name that shows up in the log messages.
    response = get_with_retry(APPDETAILS_URL, params, f"appid {appid}")
    # Steam answers {"<appid>": {"success": ..., "data": {...}}}. The key is the
    # appid as TEXT, and the whole answer can be `null`. `x or {}` means "use x,
    # but if it is empty or None, use an empty dict", so nothing crashes.
    entry = (response.json() or {}).get(str(appid)) or {}
    # A 200 can still mean "game not found". Then `success` is false.
    return entry.get("data") if entry.get("success") else None


def get_with_retry(
    url: str,
    params: dict,
    label: str,
    accept_statuses: tuple[int, ...] = (),
) -> requests.Response:
    """Send a GET request and try again if Steam is busy.

    We retry when the request times out, or when Steam answers 429 (too many
    requests) or 5xx (a problem on Steam's side). The wait grows each time.

    A status in `accept_statuses` (for example 404) is returned as a normal
    answer instead of an error, because some endpoints use it to say "no data".

    Raises SteamRateLimitError if the last attempt was still a 429, and
    SteamRequestError if the request still failed after all attempts.
    """
    problem = ""  # what went wrong on the last attempt, used in the messages

    for attempt in range(1, MAX_ATTEMPTS + 1):  # attempt is 1, then 2, then 3
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        except (requests.Timeout, requests.ConnectionError) as error:
            problem = type(error).__name__  # for example "Timeout"
        else:  # no network error, so Steam answered
            if response.status_code == 429 or response.status_code >= 500:
                problem = f"HTTP {response.status_code}"  # busy or broken: retry
            else:
                if response.status_code not in accept_statuses:
                    # Any other 4xx (for example 403) is our own mistake.
                    # Stop with an error, do not retry.
                    response.raise_for_status()
                return response  # a good answer, so we are done

        # We only get here after a problem: wait, then the loop tries again.
        if attempt < MAX_ATTEMPTS:  # no need to wait after the last attempt
            wait = BACKOFF_SECONDS * attempt  # 30 s, then 60 s
            logger.warning(
                "%s: %s (attempt %s/%s), waiting %ss",
                label,
                problem,
                attempt,
                MAX_ATTEMPTS,
                wait,
            )
            time.sleep(wait)

    # All attempts are used up, so we stop with an error.
    message = f"{label}: {problem} after {MAX_ATTEMPTS} attempts"
    if problem == "HTTP 429":
        raise SteamRateLimitError(message)
    raise SteamRequestError(message)


def fetch_review_summary(appid: int) -> dict | None:
    """Ask Steam for the review totals of ONE game.

    Steam also sends single reviews, but we only want the totals. So we ask for
    1 review per page and keep only the totals block (`query_summary`).
    Returns that block, or None if the answer has no usable totals.
    """
    # Steam wants the options as JSON text in one parameter called `input_json`.
    # "languages" is a list. With ["all"] Steam counts reviews in every language.
    # We used to send "language": "all", which Steam ignores, so it counted
    # English reviews only. Fixed on 2026-11-02, so rows before that are English only.
    options = {"appid": appid, "num_per_page": 1, "languages": ["all"]}
    response = get_with_retry(
        REVIEWS_URL, {"input_json": json.dumps(options)}, f"appid {appid}"
    )
    try:
        body = response.json()
    except ValueError:  # the answer was not JSON
        return None
    if not isinstance(body, dict):  # we expect an object like {...}
        return None
    summary = (body.get("response") or {}).get("query_summary")
    # No dict, or no `total_reviews` inside it, means no usable totals.
    if not isinstance(summary, dict) or "total_reviews" not in summary:
        return None
    return summary


def fetch_player_count(appid: int) -> dict | None:
    """Ask Steam how many players ONE game has right now.

    Returns {"player_count": number or None, "result": number}.
    For an unreleased game or a wrong id, Steam answers 404 with result 42 and
    no player_count. That means "no data", not "0 players", so the count stays
    None. Returns None if the answer is not usable at all.
    """
    # A 404 is a normal answer here ("no data"), so we accept it.
    response = get_with_retry(
        PLAYERS_URL, {"appid": appid}, f"appid {appid}", accept_statuses=(404,)
    )
    try:
        body = response.json()
    except ValueError:  # the answer was not JSON
        return None
    if not isinstance(body, dict):
        return None
    # `response` must be a dict, and its `result` must be a whole number.
    block = body.get("response")
    if not isinstance(block, dict) or not isinstance(block.get("result"), int):
        return None
    # The count may be missing (None). If it is there, it must be a whole number.
    count = block.get("player_count")
    if count is not None and not isinstance(count, int):
        return None
    return {"player_count": count, "result": block["result"]}


def fetch_recent_review_count(appid: int, review_type: int) -> int | None:
    """Ask Steam how many reviews ONE game got in the last RECENT_DAYS days.

    `review_type` is 1 for positive reviews and 2 for negative ones. Steam
    cannot send only a count, so we ask for 1 review per page and read the
    number in `total_matching`, which counts all reviews that fit the question.
    Returns that whole number, or None if the answer has no usable count.
    """
    options = {
        "appid": appid,
        "num_per_page": 1,
        "day_range": RECENT_DAYS,
        # "languages" must be a list. Without it Steam counts English reviews only.
        "languages": ["all"],
        "review_type": review_type,
    }
    response = get_with_retry(
        REVIEWS_URL, {"input_json": json.dumps(options)}, f"appid {appid}"
    )
    try:
        body = response.json()
    except ValueError:  # the answer was not JSON
        return None
    if not isinstance(body, dict):  # we expect an object like {...}
        return None
    block = body.get("response")
    if not isinstance(block, dict):
        return None
    count = block.get("total_matching")
    # In Python, True counts as a number too, so we rule it out on purpose.
    if not isinstance(count, int) or isinstance(count, bool):
        return None
    return count


def fetch_achievements(appid: int) -> list | None:
    """Ask Steam for the achievement percentages of ONE game.

    Returns the list of achievements (each has a `name` and a `percent`).
    Returns an empty list when Steam has no data: it answers HTTP 403 with an
    empty `{}` for an unreleased game or a wrong id. Any other 403 is a real
    problem, so it raises an error. Returns None if the answer is not usable.
    """
    response = get_with_retry(
        ACHIEVEMENTS_URL, {"gameid": appid}, f"appid {appid}", accept_statuses=(403,)
    )
    if response.status_code == 403:
        try:
            is_empty = response.json() == {}
        except ValueError:  # the answer was not JSON
            is_empty = False
        if not is_empty:
            response.raise_for_status()  # a real block, not "no data"
        return []
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    block = body.get("achievementpercentages")
    if not isinstance(block, dict):
        return None
    items = block.get("achievements")
    if not isinstance(items, list):
        return None
    return items


def build_game_row(data: dict, collected_at: datetime) -> dict:
    """Turn Steam's answer for one game into one flat row (a dict).

    We keep only the fields we need. Prices stay as Steam sends them: whole
    numbers in cents (969 = 9.69 EUR). Free and unreleased games have no price,
    so the price fields can be None.
    """
    # `.get(key, default)` gives the default if the key is missing, so a missing
    # field does not crash the code.
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
        # These four are lists. They are saved as JSON in one column
        # (see `columns` on the `games` resource below).
        "developers": data.get("developers", []),
        "publishers": data.get("publishers", []),
        # Steam sends genres and categories as small objects. We keep the text.
        "genres": [g["description"] for g in data.get("genres", [])],
        "categories": [c["description"] for c in data.get("categories", [])],
    }


def build_review_row(appid: int, summary: dict, collected_at: datetime) -> dict:
    """Make one row from the review totals, as Steam sends them.

    That means the counts, a score from 0 to 9, and a label like "Very Positive".
    """
    return {
        "steam_appid": appid,
        "collected_at": collected_at,
        "review_score": summary.get("review_score"),
        "review_score_desc": summary.get("review_score_desc"),
        "total_positive": summary.get("total_positive"),
        "total_negative": summary.get("total_negative"),
        "total_reviews": summary.get("total_reviews"),
    }


def build_player_row(appid: int, answer: dict, collected_at: datetime) -> dict:
    """Make one row from the player count. A missing count stays None, not 0."""
    return {
        "steam_appid": appid,
        "collected_at": collected_at,
        "player_count": answer["player_count"],
        "result": answer["result"],
    }


def build_review_recent_row(
    appid: int, positive: int, negative: int, collected_at: datetime
) -> dict:
    """Make one row from the recent review counts, as Steam sends them.

    We do not store the total. It is positive + negative, and dbt adds it later.
    """
    return {
        "steam_appid": appid,
        "collected_at": collected_at,
        "day_range": RECENT_DAYS,
        "recent_positive": positive,
        "recent_negative": negative,
    }


def build_achievement_rows(appid: int, items: list, collected_at: datetime) -> list:
    """Make one row per achievement. A bad entry is left out.

    Steam sends `percent` as text (for example "40.9"). We keep it as text, and
    dbt turns it into a number later.
    """
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        percent = item.get("percent")
        if not isinstance(name, str) or not name or percent is None:
            continue
        rows.append(
            {
                "steam_appid": appid,
                "collected_at": collected_at,
                "achievement_name": name,
                "percent": str(percent),
            }
        )
    return rows


@dlt.resource(
    name="games",
    # append = add new rows on every run and keep the old ones,
    # so price changes build up a history.
    write_disposition="append",
    columns={
        # We set the type ourselves instead of letting dlt guess it.
        "collected_at": {"data_type": "timestamp"},
        # Save these lists as JSON in one column. Without this, dlt would make
        # extra child tables.
        "developers": {"data_type": "json"},
        "publishers": {"data_type": "json"},
        "genres": {"data_type": "json"},
        "categories": {"data_type": "json"},
    },
)
def games(appids: list[int]) -> Iterator[dict]:
    """Give dlt one row per game each time the pipeline runs.

    A game that fails is logged and skipped, so one bad game does not lose the
    run. If Steam keeps answering 429, we stop the whole run instead of asking
    more.
    """
    collected_at = datetime.now(UTC)  # one time for the whole run
    fetched = skipped = failed = 0  # counters for the summary line at the end

    # `position` counts 0, 1, 2, ... and `appid` is the game.
    for position, appid in enumerate(appids):
        if position > 0:  # no wait before the first game
            if position % PROGRESS_EVERY == 0:  # every 10 games
                logger.info("games: %s of %s games done", position, len(appids))
            time.sleep(REQUEST_PAUSE_SECONDS)  # a pause between requests
        try:
            data = fetch_app_details(appid)
        except SteamRateLimitError:
            logger.error("Steam rate limit hit at appid %s; stopping the run", appid)
            raise  # raise it again, which stops the whole run
        except (SteamRequestError, requests.RequestException) as error:
            failed += 1
            logger.error("appid %s: failed, skipping (%s)", appid, error)
            continue  # skip this game and go to the next one

        if data is None:  # Steam said success = false
            skipped += 1
            logger.warning("appid %s: Steam returned success=false, skipping", appid)
            continue

        fetched += 1
        # `yield` hands one row to dlt, then the loop goes on with the next game.
        yield build_game_row(data, collected_at)

    # The summary line at the end of the run.
    logger.info(
        "games: %s fetched, %s skipped (success=false), %s failed, of %s requested",
        fetched,
        skipped,
        failed,
        len(appids),
    )


@dlt.resource(
    name="review_summary",
    # append = one new row per game per run, so review scores build up a history.
    write_disposition="append",
    columns={"collected_at": {"data_type": "timestamp"}},
)
def review_summary(appids: list[int]) -> Iterator[dict]:
    """Give dlt one row per game each time the pipeline runs, with the review totals.

    A game that fails is logged and skipped. If Steam keeps answering 429, we
    stop the whole run instead of asking more.
    """
    collected_at = datetime.now(UTC)  # one time for the whole run
    fetched = skipped = failed = 0  # counters for the summary line at the end

    for position, appid in enumerate(appids):
        if position > 0:
            if position % PROGRESS_EVERY == 0:  # every 10 games
                logger.info(
                    "review_summary: %s of %s games done", position, len(appids)
                )
            time.sleep(REQUEST_PAUSE_SECONDS)
        try:
            summary = fetch_review_summary(appid)
        except SteamRateLimitError:
            logger.error("Steam rate limit hit at appid %s; stopping the run", appid)
            raise  # stops the whole run
        except (SteamRequestError, requests.RequestException) as error:
            failed += 1
            logger.error("appid %s: failed, skipping (%s)", appid, error)
            continue  # skip this game and go to the next one

        if summary is None:  # Steam sent no usable totals
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


@dlt.resource(
    name="player_counts",
    # append = one new row per game per run, so player activity builds up a history.
    write_disposition="append",
    columns={
        "collected_at": {"data_type": "timestamp"},
        # We set the types ourselves. If every count in a batch is NULL, dlt would
        # have nothing to guess the type from.
        "player_count": {"data_type": "bigint"},
        "result": {"data_type": "bigint"},
    },
)
def player_counts(appids: list[int]) -> Iterator[dict]:
    """Give dlt one row per game each time the pipeline runs: the players right now.

    A game Steam has no data for (result 42) still gets a row, with a NULL
    count. A game that fails is logged and skipped. If Steam keeps answering
    429, we stop the whole run instead of asking more.
    """
    # Counters for the summary line at the end.
    with_count = no_data = skipped = failed = 0

    for position, appid in enumerate(appids):
        if position > 0:
            if position % PROGRESS_EVERY == 0:  # every 10 games
                logger.info("player_counts: %s of %s games done", position, len(appids))
            time.sleep(REQUEST_PAUSE_SECONDS)
        try:
            answer = fetch_player_count(appid)
        except SteamRateLimitError:
            logger.error("Steam rate limit hit at appid %s; stopping the run", appid)
            raise  # stops the whole run
        except (SteamRequestError, requests.RequestException) as error:
            failed += 1
            logger.error("appid %s: failed, skipping (%s)", appid, error)
            continue  # skip this game and go to the next one
        # A player count is one moment. So each row gets its own time, taken right
        # after Steam answered, and not one time for the whole run.
        collected_at = datetime.now(UTC)

        if answer is None:  # the answer was not usable
            skipped += 1
            logger.warning("appid %s: unusable player count answer, skipping", appid)
            continue

        if answer["player_count"] is None:  # no data (result 42)
            no_data += 1
        else:
            with_count += 1
        yield build_player_row(appid, answer, collected_at)

    logger.info(
        "player_counts: %s with a count, %s without data, %s skipped, %s failed, "
        "of %s requested",
        with_count,
        no_data,
        skipped,
        failed,
        len(appids),
    )


@dlt.resource(
    name="review_recent",
    # append = one new row per game per run, so the recent reviews build a history.
    write_disposition="append",
    columns={"collected_at": {"data_type": "timestamp"}},
)
def review_recent(appids: list[int]) -> Iterator[dict]:
    """Give dlt one row per game each time the pipeline runs.

    Each row has the positive and negative reviews of the last RECENT_DAYS days.
    That takes two requests per game. If either count is not usable, we skip
    the game, so we never store half a pair. A game that fails is logged and
    skipped. If Steam keeps answering 429, we stop the whole run.
    """
    collected_at = datetime.now(UTC)  # one time for the whole run
    fetched = skipped = failed = 0  # counters for the summary line at the end

    for position, appid in enumerate(appids):
        if position > 0:
            if position % PROGRESS_EVERY == 0:  # every 10 games
                logger.info("review_recent: %s of %s games done", position, len(appids))
            time.sleep(REQUEST_PAUSE_SECONDS)
        try:
            positive = fetch_recent_review_count(appid, REVIEW_TYPE_POSITIVE)
            negative = None
            if positive is not None:  # no point in asking the second question
                time.sleep(REQUEST_PAUSE_SECONDS)  # a pause between the two requests
                negative = fetch_recent_review_count(appid, REVIEW_TYPE_NEGATIVE)
        except SteamRateLimitError:
            logger.error("Steam rate limit hit at appid %s; stopping the run", appid)
            raise  # stops the whole run
        except (SteamRequestError, requests.RequestException) as error:
            failed += 1
            logger.error("appid %s: failed, skipping (%s)", appid, error)
            continue  # skip this game and go to the next one

        if positive is None or negative is None:  # a count was not usable
            skipped += 1
            logger.warning("appid %s: no usable recent review counts, skipping", appid)
            continue

        fetched += 1
        yield build_review_recent_row(appid, positive, negative, collected_at)

    logger.info(
        "review_recent: %s fetched, %s skipped (no usable count), %s failed, "
        "of %s requested",
        fetched,
        skipped,
        failed,
        len(appids),
    )


@dlt.resource(
    name="achievements",
    # append = new rows on every run, so the percentages build a history.
    write_disposition="append",
    columns={
        "collected_at": {"data_type": "timestamp"},
        # Steam sends the percent as text. We fix the type so dlt never splits
        # the column in two if a number shows up one day.
        "percent": {"data_type": "text"},
    },
)
def achievements(appids: list[int]) -> Iterator[dict]:
    """Give dlt one row per game and achievement each time the pipeline runs.

    A game Steam has no data for (unreleased, wrong id, or no achievements)
    gets no rows. That is not the same as 0 percent. A game that fails is
    logged and skipped. If Steam keeps answering 429, we stop the whole run.
    """
    collected_at = datetime.now(UTC)  # one time for the whole run
    # Counters for the summary line at the end.
    with_rows = no_data = skipped = failed = row_count = 0

    for position, appid in enumerate(appids):
        if position > 0:
            if position % PROGRESS_EVERY == 0:  # every 10 games
                logger.info("achievements: %s of %s games done", position, len(appids))
            time.sleep(REQUEST_PAUSE_SECONDS)
        try:
            items = fetch_achievements(appid)
        except SteamRateLimitError:
            logger.error("Steam rate limit hit at appid %s; stopping the run", appid)
            raise  # stops the whole run
        except (SteamRequestError, requests.RequestException) as error:
            failed += 1
            logger.error("appid %s: failed, skipping (%s)", appid, error)
            continue  # skip this game and go to the next one

        if items is None:  # the answer was not usable
            skipped += 1
            logger.warning("appid %s: unusable achievements answer, skipping", appid)
            continue

        rows = build_achievement_rows(appid, items, collected_at)
        if len(rows) < len(items):
            logger.warning(
                "appid %s: left out %s bad achievement entries",
                appid,
                len(items) - len(rows),
            )
        if not rows:  # Steam has no achievements for this game
            no_data += 1
            continue

        with_rows += 1
        row_count += len(rows)
        yield from rows

    logger.info(
        "achievements: %s games with rows (%s rows), %s without data, "
        "%s skipped, %s failed, of %s requested",
        with_rows,
        row_count,
        no_data,
        skipped,
        failed,
        len(appids),
    )


@dlt.source(name="steam")
def steam_source(appids: list[int]):
    """Bundle the five resources, so dlt loads them together in one run."""
    return (
        games(appids),
        review_summary(appids),
        player_counts(appids),
        review_recent(appids),
        achievements(appids),
    )
