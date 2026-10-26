"""Tests for the Steam ingestion. No real network and no Snowflake."""

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


def test_build_game_row_free_game_has_no_price():
    data = {"steam_appid": 1, "name": "Free Game", "is_free": True}

    row = steam.build_game_row(data, COLLECTED_AT)

    assert row["steam_appid"] == 1
    assert row["price_final"] is None
    assert row["developers"] == []
