"""Tests for the Steam ingestion. No real network and no Snowflake."""

import json
from datetime import UTC, datetime

import pytest
import requests
from dlt.extract.exceptions import ResourceExtractionError

from steam_data_platform.ingestion import steam

COLLECTED_AT = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

GOOD_SUMMARY = {
    "num_reviews": 1,
    "review_score": 8,
    "review_score_desc": "Very Positive",
    "total_positive": 90,
    "total_negative": 10,
    "total_reviews": 100,
}


class FakeResponse:
    """A hand-written stand-in for requests.Response."""

    def __init__(self, status_code=200, body=None, json_error=False):
        self.status_code = status_code
        self._body = body
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("not JSON")
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture
def sleeps(monkeypatch) -> list[float]:
    """Make time.sleep instant; the list holds the waits that were asked for."""
    waits: list[float] = []
    monkeypatch.setattr(steam.time, "sleep", waits.append)
    return waits


@pytest.fixture
def patch_get(monkeypatch):
    """Return a function that makes requests.get answer from a list, in order."""

    def _patch(answers: list) -> list[str]:
        queue = list(answers)
        calls: list[str] = []

        def fake_get(url, params=None, timeout=None):
            calls.append(url)
            answer = queue.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

        monkeypatch.setattr(steam.requests, "get", fake_get)
        return calls

    return _patch


# --- get_with_retry -------------------------------------------------------


def test_get_with_retry_returns_a_good_response(patch_get, sleeps):
    ok = FakeResponse(200, {"a": 1})
    calls = patch_get([ok])

    assert steam.get_with_retry("http://x", {}, "test") is ok
    assert len(calls) == 1
    assert sleeps == []


def test_get_with_retry_retries_429_then_succeeds(patch_get, sleeps):
    ok = FakeResponse(200, {})
    patch_get([FakeResponse(429), ok])

    assert steam.get_with_retry("http://x", {}, "test") is ok
    assert sleeps == [steam.BACKOFF_SECONDS]


def test_get_with_retry_retries_a_timeout(patch_get, sleeps):
    ok = FakeResponse(200, {})
    patch_get([requests.Timeout(), ok])

    assert steam.get_with_retry("http://x", {}, "test") is ok
    assert len(sleeps) == 1


def test_get_with_retry_raises_rate_limit_after_all_attempts(patch_get, sleeps):
    calls = patch_get([FakeResponse(429)] * steam.MAX_ATTEMPTS)

    with pytest.raises(steam.SteamRateLimitError):
        steam.get_with_retry("http://x", {}, "test")
    assert len(calls) == steam.MAX_ATTEMPTS
    # The waits grow: 30 s after attempt 1, 60 s after attempt 2.
    assert sleeps == [30, 60]


def test_get_with_retry_server_error_is_not_a_rate_limit(patch_get, sleeps):
    patch_get([FakeResponse(500)] * steam.MAX_ATTEMPTS)

    with pytest.raises(steam.SteamRequestError) as error:
        steam.get_with_retry("http://x", {}, "test")
    assert not isinstance(error.value, steam.SteamRateLimitError)


def test_get_with_retry_does_not_retry_other_4xx(patch_get, sleeps):
    calls = patch_get([FakeResponse(404)])

    with pytest.raises(requests.HTTPError):
        steam.get_with_retry("http://x", {}, "test")
    assert len(calls) == 1


# --- fetch_review_summary -------------------------------------------------


def test_fetch_review_summary_returns_the_summary(patch_get, sleeps):
    patch_get([FakeResponse(200, {"response": {"query_summary": GOOD_SUMMARY}})])

    assert steam.fetch_review_summary(281990) == GOOD_SUMMARY


def test_fetch_review_summary_keeps_zero_counts(patch_get, sleeps):
    """An unreleased game has real zeros; they must not be treated as missing."""
    zeros = {**GOOD_SUMMARY, "total_positive": 0, "total_negative": 0}
    zeros["total_reviews"] = 0
    patch_get([FakeResponse(200, {"response": {"query_summary": zeros}})])

    assert steam.fetch_review_summary(1257610) == zeros


@pytest.mark.parametrize(
    "body",
    [
        {"response": {}},  # no query_summary (what a fake appid gave us)
        {"response": {"query_summary": {"num_reviews": 5}}},  # no totals
        {},
        [],
        None,
    ],
)
def test_fetch_review_summary_returns_none_for_unusable_answers(
    patch_get, sleeps, body
):
    patch_get([FakeResponse(200, body)])

    assert steam.fetch_review_summary(99999999) is None


def test_fetch_review_summary_returns_none_when_not_json(patch_get, sleeps):
    patch_get([FakeResponse(200, json_error=True)])

    assert steam.fetch_review_summary(1) is None


def test_fetch_review_summary_asks_for_all_languages(monkeypatch, sleeps):
    """Steam ignores "language". It must be "languages", as a list."""
    asked: list[dict] = []

    def fake_get(url, params=None, timeout=None):
        asked.append(json.loads(params["input_json"]))
        return FakeResponse(200, {"response": {"query_summary": GOOD_SUMMARY}})

    monkeypatch.setattr(steam.requests, "get", fake_get)

    steam.fetch_review_summary(281990)

    assert asked == [{"appid": 281990, "num_per_page": 1, "languages": ["all"]}]


# --- build_review_row -----------------------------------------------------


def test_build_review_row_keeps_the_totals():
    row = steam.build_review_row(281990, GOOD_SUMMARY, COLLECTED_AT)

    assert row == {
        "steam_appid": 281990,
        "collected_at": COLLECTED_AT,
        "review_score": 8,
        "review_score_desc": "Very Positive",
        "total_positive": 90,
        "total_negative": 10,
        "total_reviews": 100,
    }


# --- review_summary resource ----------------------------------------------


def test_review_summary_skips_bad_games_and_keeps_good_ones(monkeypatch, sleeps):
    def fake_fetch(appid):
        if appid == 2:
            return None  # Steam gave no summary
        if appid == 3:
            raise steam.SteamRequestError("boom")  # failed after retries
        return GOOD_SUMMARY

    monkeypatch.setattr(steam, "fetch_review_summary", fake_fetch)

    rows = list(steam.review_summary([1, 2, 3, 4]))

    assert [row["steam_appid"] for row in rows] == [1, 4]
    # Every row of one run shares the same collected_at.
    assert len({row["collected_at"] for row in rows}) == 1


def test_review_summary_stops_the_run_on_rate_limit(monkeypatch, sleeps):
    asked: list[int] = []

    def fake_fetch(appid):
        asked.append(appid)
        if appid == 2:
            raise steam.SteamRateLimitError("429")
        return GOOD_SUMMARY

    monkeypatch.setattr(steam, "fetch_review_summary", fake_fetch)

    # dlt wraps errors from inside a resource; ours is the cause.
    with pytest.raises(ResourceExtractionError) as error:
        list(steam.review_summary([1, 2, 3]))
    assert isinstance(error.value.__cause__, steam.SteamRateLimitError)
    assert asked == [1, 2]  # game 3 was never requested


# --- games (appdetails) ---------------------------------------------------


def test_fetch_app_details_returns_none_when_success_is_false(patch_get, sleeps):
    patch_get([FakeResponse(200, {"99999999": {"success": False}})])

    assert steam.fetch_app_details(99999999) is None


def test_fetch_app_details_returns_the_data(patch_get, sleeps):
    data = {"steam_appid": 281990, "name": "Stellaris"}
    patch_get([FakeResponse(200, {"281990": {"success": True, "data": data}})])

    assert steam.fetch_app_details(281990) == data


def test_fetch_app_details_returns_none_when_the_body_is_null(patch_get, sleeps):
    """Steam can answer with `null` instead of an object; that must not crash."""
    patch_get([FakeResponse(200, None)])

    assert steam.fetch_app_details(1) is None


def test_fetch_app_details_retries_through_get_with_retry(patch_get, sleeps):
    """A 429 is retried (with the shared wait), then the good answer is used."""
    data = {"steam_appid": 281990}
    calls = patch_get(
        [
            FakeResponse(429),
            FakeResponse(200, {"281990": {"success": True, "data": data}}),
        ]
    )

    assert steam.fetch_app_details(281990) == data
    assert len(calls) == 2
    assert sleeps == [steam.BACKOFF_SECONDS]


def test_build_game_row_free_game_has_no_price():
    data = {"steam_appid": 1, "name": "Free Game", "is_free": True}

    row = steam.build_game_row(data, COLLECTED_AT)

    assert row["steam_appid"] == 1
    assert row["price_final"] is None
    assert row["developers"] == []


# --- get_with_retry: accept_statuses --------------------------------------


def test_get_with_retry_returns_an_accepted_status_without_retrying(patch_get, sleeps):
    not_found = FakeResponse(404, {"response": {"result": 42}})
    calls = patch_get([not_found])

    assert (
        steam.get_with_retry("http://x", {}, "test", accept_statuses=(404,))
        is not_found
    )
    assert len(calls) == 1
    assert sleeps == []


def test_get_with_retry_accept_statuses_does_not_cover_other_4xx(patch_get, sleeps):
    calls = patch_get([FakeResponse(403)])

    with pytest.raises(requests.HTTPError):
        steam.get_with_retry("http://x", {}, "test", accept_statuses=(404,))
    assert len(calls) == 1


# --- fetch_player_count ---------------------------------------------------

GOOD_PLAYERS = {"player_count": 7992, "result": 1}
NO_DATA_PLAYERS = {"player_count": None, "result": 42}


def test_fetch_player_count_returns_the_count(patch_get, sleeps):
    patch_get([FakeResponse(200, {"response": {"player_count": 7992, "result": 1}})])

    assert steam.fetch_player_count(281990) == GOOD_PLAYERS


def test_fetch_player_count_keeps_zero_as_zero(patch_get, sleeps):
    """Zero players is a real answer; it must not turn into None."""
    patch_get([FakeResponse(200, {"response": {"player_count": 0, "result": 1}})])

    answer = steam.fetch_player_count(1)

    assert answer == {"player_count": 0, "result": 1}
    assert answer["player_count"] is not None


def test_fetch_player_count_404_is_no_data_not_zero(patch_get, sleeps):
    """Steam answers 404 with result 42 for unreleased games and wrong ids."""
    calls = patch_get([FakeResponse(404, {"response": {"result": 42}})])

    assert steam.fetch_player_count(1257610) == NO_DATA_PLAYERS
    assert len(calls) == 1  # a 404 is an answer, not something to retry


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        None,
        {"response": []},
        {"response": {"player_count": 5}},  # no result code
        {"response": {"result": "1"}},  # result is not a number
        {"response": {"result": 1, "player_count": "12"}},  # count is not a number
    ],
)
def test_fetch_player_count_returns_none_for_unusable_answers(patch_get, sleeps, body):
    patch_get([FakeResponse(200, body)])

    assert steam.fetch_player_count(1) is None


def test_fetch_player_count_returns_none_when_not_json(patch_get, sleeps):
    patch_get([FakeResponse(200, json_error=True)])

    assert steam.fetch_player_count(1) is None


# --- build_player_row -----------------------------------------------------


def test_build_player_row_keeps_a_missing_count_as_none():
    row = steam.build_player_row(1257610, NO_DATA_PLAYERS, COLLECTED_AT)

    assert row == {
        "steam_appid": 1257610,
        "collected_at": COLLECTED_AT,
        "player_count": None,
        "result": 42,
    }


# --- player_counts resource -----------------------------------------------


def test_player_counts_keeps_zero_and_no_data_and_skips_bad_games(monkeypatch, sleeps):
    answers = {
        1: GOOD_PLAYERS,
        2: {"player_count": 0, "result": 1},
        3: NO_DATA_PLAYERS,
    }

    def fake_fetch(appid):
        if appid == 4:
            return None  # unusable answer
        if appid == 5:
            raise steam.SteamRequestError("boom")  # failed after retries
        return answers[appid]

    monkeypatch.setattr(steam, "fetch_player_count", fake_fetch)

    rows = list(steam.player_counts([1, 2, 3, 4, 5]))

    assert [row["steam_appid"] for row in rows] == [1, 2, 3]
    # 0 players and "no data" stay apart.
    assert [row["player_count"] for row in rows] == [7992, 0, None]
    assert [row["result"] for row in rows] == [1, 1, 42]
    # Each row has its own time, taken in order.
    times = [row["collected_at"] for row in rows]
    assert all(time.tzinfo is not None for time in times)
    assert times == sorted(times)


def test_player_counts_stops_the_run_on_rate_limit(monkeypatch, sleeps):
    asked: list[int] = []

    def fake_fetch(appid):
        asked.append(appid)
        if appid == 2:
            raise steam.SteamRateLimitError("429")
        return GOOD_PLAYERS

    monkeypatch.setattr(steam, "fetch_player_count", fake_fetch)

    with pytest.raises(ResourceExtractionError) as error:
        list(steam.player_counts([1, 2, 3]))
    assert isinstance(error.value.__cause__, steam.SteamRateLimitError)
    assert asked == [1, 2]  # game 3 was never requested


# --- fetch_recent_review_count --------------------------------------------


def test_fetch_recent_review_count_returns_total_matching(patch_get, sleeps):
    patch_get([FakeResponse(200, {"response": {"total_matching": 363}})])

    assert steam.fetch_recent_review_count(281990, steam.REVIEW_TYPE_POSITIVE) == 363


def test_fetch_recent_review_count_asks_the_right_question(monkeypatch, sleeps):
    """The question must name the days, all languages and the review type."""
    asked: list[dict] = []

    def fake_get(url, params=None, timeout=None):
        asked.append(json.loads(params["input_json"]))
        return FakeResponse(200, {"response": {"total_matching": 5}})

    monkeypatch.setattr(steam.requests, "get", fake_get)

    steam.fetch_recent_review_count(281990, steam.REVIEW_TYPE_NEGATIVE)

    assert asked == [
        {
            "appid": 281990,
            "num_per_page": 1,
            "day_range": 30,
            "languages": ["all"],
            "review_type": 2,
        }
    ]


def test_fetch_recent_review_count_keeps_zero_as_zero(patch_get, sleeps):
    """No recent reviews is a real 0. It must not turn into None."""
    patch_get([FakeResponse(200, {"response": {"total_matching": 0}})])

    count = steam.fetch_recent_review_count(1, steam.REVIEW_TYPE_POSITIVE)

    assert count == 0
    assert count is not None


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        None,
        {"response": []},
        {"response": {}},  # no total_matching
        {"response": {"total_matching": "12"}},  # a text, not a number
        {"response": {"total_matching": True}},  # True is not a count
    ],
)
def test_fetch_recent_review_count_returns_none_for_unusable_answers(
    patch_get, sleeps, body
):
    patch_get([FakeResponse(200, body)])

    assert steam.fetch_recent_review_count(1, steam.REVIEW_TYPE_POSITIVE) is None


def test_fetch_recent_review_count_returns_none_when_not_json(patch_get, sleeps):
    patch_get([FakeResponse(200, json_error=True)])

    assert steam.fetch_recent_review_count(1, steam.REVIEW_TYPE_POSITIVE) is None


# --- build_review_recent_row ----------------------------------------------


def test_build_review_recent_row_keeps_the_counts():
    row = steam.build_review_recent_row(281990, 363, 195, COLLECTED_AT)

    assert row == {
        "steam_appid": 281990,
        "collected_at": COLLECTED_AT,
        "day_range": 30,
        "recent_positive": 363,
        "recent_negative": 195,
    }


# --- review_recent resource -----------------------------------------------


def test_review_recent_skips_bad_games_and_keeps_zero(monkeypatch, sleeps):
    asked: list[tuple[int, int]] = []

    def fake_fetch(appid, review_type):
        asked.append((appid, review_type))
        if appid == 2:
            return None  # the positive count is not usable
        if appid == 3:
            raise steam.SteamRequestError("boom")  # failed after retries
        if appid == 4 and review_type == steam.REVIEW_TYPE_NEGATIVE:
            return None  # only the negative count is not usable
        if appid == 5:
            return 0  # a real zero
        return 10 if review_type == steam.REVIEW_TYPE_POSITIVE else 4

    monkeypatch.setattr(steam, "fetch_recent_review_count", fake_fetch)

    rows = list(steam.review_recent([1, 2, 3, 4, 5]))

    # Games 2, 3 and 4 are left out, so we never store half a pair.
    assert [row["steam_appid"] for row in rows] == [1, 5]
    assert (rows[0]["recent_positive"], rows[0]["recent_negative"]) == (10, 4)
    assert (rows[1]["recent_positive"], rows[1]["recent_negative"]) == (0, 0)
    # Every row of one run shares the same collected_at.
    assert len({row["collected_at"] for row in rows}) == 1
    # Game 2 had no usable positive count, so we did not ask the second question.
    assert (2, steam.REVIEW_TYPE_NEGATIVE) not in asked


def test_review_recent_stops_the_run_on_rate_limit(monkeypatch, sleeps):
    asked: list[int] = []

    def fake_fetch(appid, review_type):
        asked.append(appid)
        if appid == 2:
            raise steam.SteamRateLimitError("429")
        return 10

    monkeypatch.setattr(steam, "fetch_recent_review_count", fake_fetch)

    with pytest.raises(ResourceExtractionError) as error:
        list(steam.review_recent([1, 2, 3]))
    assert isinstance(error.value.__cause__, steam.SteamRateLimitError)
    assert 3 not in asked  # game 3 was never requested


# --- fetch_achievements ---------------------------------------------------

GOOD_ACHIEVEMENTS = [
    {"name": "achievement_economy_1", "percent": "40.9"},
    {"name": "achievement_colonize", "percent": "36.5"},
]


def test_fetch_achievements_returns_the_list(patch_get, sleeps):
    body = {"achievementpercentages": {"achievements": GOOD_ACHIEVEMENTS}}
    patch_get([FakeResponse(200, body)])

    assert steam.fetch_achievements(281990) == GOOD_ACHIEVEMENTS


def test_fetch_achievements_403_with_empty_body_is_no_data(patch_get, sleeps):
    """Unreleased games and wrong ids give 403 and {}. That is an answer."""
    calls = patch_get([FakeResponse(403, {})])

    assert steam.fetch_achievements(1257610) == []
    assert len(calls) == 1  # a 403 is an answer, not something to retry


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(403, {"error": "blocked"}),  # not empty
        FakeResponse(403, json_error=True),  # not JSON
    ],
)
def test_fetch_achievements_other_403_is_an_error(patch_get, sleeps, response):
    patch_get([response])

    with pytest.raises(requests.HTTPError):
        steam.fetch_achievements(1)


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        None,
        {"achievementpercentages": []},
        {"achievementpercentages": {}},  # no achievements key
        {"achievementpercentages": {"achievements": "none"}},  # not a list
    ],
)
def test_fetch_achievements_returns_none_for_unusable_answers(patch_get, sleeps, body):
    patch_get([FakeResponse(200, body)])

    assert steam.fetch_achievements(1) is None


def test_fetch_achievements_returns_none_when_not_json(patch_get, sleeps):
    patch_get([FakeResponse(200, json_error=True)])

    assert steam.fetch_achievements(1) is None


# --- build_achievement_rows -----------------------------------------------


def test_build_achievement_rows_keeps_the_percent_as_text():
    rows = steam.build_achievement_rows(281990, GOOD_ACHIEVEMENTS, COLLECTED_AT)

    assert len(rows) == 2
    assert rows[0] == {
        "steam_appid": 281990,
        "collected_at": COLLECTED_AT,
        "achievement_name": "achievement_economy_1",
        "percent": "40.9",
    }


def test_build_achievement_rows_turns_a_number_into_text():
    """If Steam ever sends a number, the column must still hold text."""
    rows = steam.build_achievement_rows(
        1, [{"name": "a", "percent": 12.5}], COLLECTED_AT
    )

    assert rows[0]["percent"] == "12.5"


def test_build_achievement_rows_leaves_out_bad_entries():
    items = [
        {"name": "good", "percent": "1.0"},
        {"percent": "2.0"},  # no name
        {"name": "no_percent"},  # no percent
        {"name": "", "percent": "3.0"},  # empty name
        "junk",  # not an object
    ]

    rows = steam.build_achievement_rows(1, items, COLLECTED_AT)

    assert [row["achievement_name"] for row in rows] == ["good"]


# --- achievements resource ------------------------------------------------


def test_achievements_gives_rows_and_skips_no_data_and_bad_games(monkeypatch, sleeps):
    def fake_fetch(appid):
        if appid == 2:
            return []  # Steam has no data for this game
        if appid == 3:
            return None  # unusable answer
        if appid == 4:
            raise steam.SteamRequestError("boom")  # failed after retries
        return GOOD_ACHIEVEMENTS

    monkeypatch.setattr(steam, "fetch_achievements", fake_fetch)

    rows = list(steam.achievements([1, 2, 3, 4]))

    # Only game 1 gives rows. Game 2 gets no rows at all, not a 0 percent row.
    assert [row["steam_appid"] for row in rows] == [1, 1]
    assert len({row["collected_at"] for row in rows}) == 1


def test_achievements_stops_the_run_on_rate_limit(monkeypatch, sleeps):
    asked: list[int] = []

    def fake_fetch(appid):
        asked.append(appid)
        if appid == 2:
            raise steam.SteamRateLimitError("429")
        return GOOD_ACHIEVEMENTS

    monkeypatch.setattr(steam, "fetch_achievements", fake_fetch)

    with pytest.raises(ResourceExtractionError) as error:
        list(steam.achievements([1, 2, 3]))
    assert isinstance(error.value.__cause__, steam.SteamRateLimitError)
    assert asked == [1, 2]  # game 3 was never requested


# --- steam_source ---------------------------------------------------------


def test_steam_source_has_the_five_resources():
    source = steam.steam_source([1])

    assert sorted(source.resources.keys()) == [
        "achievements",
        "games",
        "player_counts",
        "review_recent",
        "review_summary",
    ]
