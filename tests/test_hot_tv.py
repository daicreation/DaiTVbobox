import importlib

import httpx

from src.models import Category, PlaySource, Quality, VideoItem


def _build_source(url: str, source_name: str, score: float = 90) -> PlaySource:
    return PlaySource(
        url=url,
        source_name=source_name,
        quality=Quality.K1080,
        score=score,
        is_available=True,
        episode_name="Episode 1",
    )


def _load_hot_tv_module():
    return importlib.import_module("src.hot_tv")


class _DummyResponse:
    def __init__(self, payload, error=None):
        self._payload = payload
        self._error = error

    def raise_for_status(self):
        if self._error is not None:
            raise self._error
        return None

    def json(self):
        return self._payload


class _DummyClient:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.closed = False

    def get(self, url, headers=None):
        if self._error is not None:
            raise self._error
        return self._response

    def close(self):
        self.closed = True


class _RoutingClient:
    def __init__(self, routes=None, error=None):
        self._routes = routes or {}
        self._error = error
        self.calls = []
        self.closed = False

    def get(self, url, headers=None, params=None):
        if self._error is not None:
            raise self._error
        params = params or {}
        key = (url, tuple(sorted(params.items())))
        self.calls.append(key)
        response = self._routes.get(key)
        if response is None:
            raise AssertionError(f"Unexpected request: {key}")
        return response

    def close(self):
        self.closed = True


def test_build_hot_tv_dataset_keeps_only_matched_titles():
    hot_tv = _load_hot_tv_module()
    feed_items = [
        {
            "title": "Hot Show A",
            "cover": "https://img.example.com/hot-show-a.jpg",
            "remarks": "Popular now",
        },
        {
            "title": "No Match Show",
            "cover": "https://img.example.com/no-match-show.jpg",
            "remarks": "Popular now",
        },
    ]
    ranked_items = [
        VideoItem(
            vod_id="tv_a",
            vod_name="Hot Show A",
            category=Category.TV,
            type_name="TV",
            sources=[_build_source("https://play.example.com/tv-a.m3u8", "storm")],
        )
    ]

    dataset = hot_tv.build_hot_tv_dataset(feed_items, ranked_items, similarity_threshold=0.8)

    assert [item["vod_name"] for item in dataset["list"]] == ["Hot Show A"]
    assert "No Match Show" not in {item["vod_name"] for item in dataset["list"]}
    detail = dataset["details"][dataset["list"][0]["vod_id"]]
    assert detail["vod_id"] == "tv_a"
    assert detail["type_name"] == "TV"
    assert detail["source_count"] == 1
    assert "https://play.example.com/tv-a.m3u8" in detail["vod_play_url"]


def test_build_hot_tv_dataset_fills_missing_titles_from_direct_sources(monkeypatch):
    hot_tv = _load_hot_tv_module()
    feed_items = [
        {
            "title": "Matched Show",
            "cover": "https://img.example.com/matched.jpg",
            "remarks": "Popular now",
        },
        {
            "title": "Missing Show",
            "cover": "https://img.example.com/missing.jpg",
            "remarks": "Popular now",
        },
    ]
    ranked_items = [
        VideoItem(
            vod_id="tv_a",
            vod_name="Matched Show",
            category=Category.TV,
            type_name="TV",
            sources=[_build_source("https://play.example.com/tv-a.m3u8", "storm")],
        )
    ]

    monkeypatch.setattr(
        hot_tv,
        "build_direct_hot_tv_dataset",
        lambda feed_items, similarity_threshold, direct_sources=None: {
            "update_time": "2026-06-26 00:00:00",
            "list": [
                {
                    "vod_id": "direct_missing",
                    "vod_name": "Missing Show",
                    "vod_pic": "https://img.example.com/missing.jpg",
                    "vod_remarks": "Popular now",
                    "source_count": 1,
                }
            ],
            "details": {
                "direct_missing": {
                    "vod_id": "direct_missing",
                    "vod_name": "Missing Show",
                    "vod_pic": "https://img.example.com/missing.jpg",
                    "vod_remarks": "Popular now",
                    "type_name": "TV",
                    "vod_year": "",
                    "vod_area": "",
                    "vod_actor": "",
                    "vod_director": "",
                    "vod_content": "",
                    "vod_score": "",
                    "source_count": 1,
                    "vod_play_from": "storm",
                    "vod_play_url": "Episode 1$https://play.example.com/direct-missing.m3u8",
                }
            },
        },
    )

    dataset = hot_tv.build_hot_tv_dataset(feed_items, ranked_items, similarity_threshold=0.8)

    assert [item["vod_name"] for item in dataset["list"]] == ["Matched Show", "Missing Show"]
    assert dataset["details"]["direct_missing"]["vod_play_url"] == "Episode 1$https://play.example.com/direct-missing.m3u8"


def test_fetch_hot_tv_feed_parses_rexxar_json(monkeypatch):
    hot_tv = _load_hot_tv_module()
    client = _DummyClient(
        response=_DummyResponse(
            {
                "subject_collection_items": [
                    {
                        "type": "tv",
                        "title": "人民的名義",
                        "year": "2017",
                        "episodes_info": "55集全",
                        "rating": {"count": 12345, "value": 8.3},
                        "pic": {
                            "large": "https://img.example.com/renmin-large.jpg",
                            "normal": "https://img.example.com/renmin-normal.jpg",
                        },
                    },
                    {
                        "type": "movie",
                        "title": "Should Be Filtered",
                        "year": "2024",
                        "pic": {"large": "https://img.example.com/movie.jpg"},
                    },
                ]
            }
        )
    )

    monkeypatch.setattr(hot_tv, "create_http_client", lambda timeout=10: client)

    items = hot_tv.fetch_hot_tv_feed()

    assert items == [
        {
            "title": "人民的名義",
            "year": "2017",
            "cover": "https://img.example.com/renmin-large.jpg",
            "remarks": "55集全 / 8.3分",
            "alt_titles": [],
        }
    ]
    assert client.closed is True


def test_fetch_hot_tv_feed_returns_empty_on_failure(monkeypatch):
    hot_tv = _load_hot_tv_module()
    client = _DummyClient(error=httpx.ConnectError("boom"))

    monkeypatch.setattr(hot_tv, "create_http_client", lambda timeout=10: client)

    assert hot_tv.fetch_hot_tv_feed() == []
    assert client.closed is True


def test_fetch_hot_tv_feed_returns_empty_on_http_error(monkeypatch):
    hot_tv = _load_hot_tv_module()
    client = _DummyClient(
        response=_DummyResponse(
            {},
            error=httpx.HTTPStatusError(
                "bad status",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(403, request=httpx.Request("GET", "https://example.com")),
            ),
        )
    )

    monkeypatch.setattr(hot_tv, "create_http_client", lambda timeout=10: client)

    assert hot_tv.fetch_hot_tv_feed() == []
    assert client.closed is True


def test_fetch_hot_tv_feed_returns_empty_on_non_dict_json(monkeypatch):
    hot_tv = _load_hot_tv_module()
    client = _DummyClient(response=_DummyResponse(["not", "a", "dict"]))

    monkeypatch.setattr(hot_tv, "create_http_client", lambda timeout=10: client)

    assert hot_tv.fetch_hot_tv_feed() == []
    assert client.closed is True


def test_fetch_hot_tv_feed_ignores_zero_rating_and_long_comment(monkeypatch):
    hot_tv = _load_hot_tv_module()
    client = _DummyClient(
        response=_DummyResponse(
            {
                "subject_collection_items": [
                    {
                        "type": "tv",
                        "title": "Zero Rating Show",
                        "year": "2025",
                        "comment": "This is a long summary that should not be used as a homepage remark.",
                        "rating": {"count": 0, "value": 0},
                        "pic": {"normal": "https://img.example.com/zero-rating.jpg"},
                    }
                ]
            }
        )
    )

    monkeypatch.setattr(hot_tv, "create_http_client", lambda timeout=10: client)

    items = hot_tv.fetch_hot_tv_feed()

    assert items == [
        {
            "title": "Zero Rating Show",
            "year": "2025",
            "cover": "https://img.example.com/zero-rating.jpg",
            "remarks": "",
            "alt_titles": [],
        }
    ]


def test_fetch_hot_tv_feed_excludes_card_subtitle_from_alt_titles(monkeypatch):
    hot_tv = _load_hot_tv_module()
    client = _DummyClient(
        response=_DummyResponse(
            {
                "subject_collection_items": [
                    {
                        "type": "tv",
                        "title": "Alias Show",
                        "year": "2025",
                        "original_title": "Real Alias",
                        "card_subtitle": "Hot Ranking Metadata",
                        "rating": {"count": 12, "value": 7.5},
                        "pic": {"normal": "https://img.example.com/alias.jpg"},
                    }
                ]
            }
        )
    )

    monkeypatch.setattr(hot_tv, "create_http_client", lambda timeout=10: client)

    items = hot_tv.fetch_hot_tv_feed()

    assert items[0]["alt_titles"] == ["Real Alias"]


def test_build_hot_tv_dataset_prefers_tv_matches():
    hot_tv = _load_hot_tv_module()
    feed_items = [
        {
            "title": "Same Name Show",
            "cover": "https://img.example.com/same-name-show.jpg",
            "remarks": "Popular now",
        }
    ]
    ranked_items = [
        VideoItem(
            vod_id="movie_match",
            vod_name="Same Name Show",
            category=Category.MOVIE,
            type_name="Movie",
            sources=[_build_source("https://play.example.com/movie.m3u8", "movie_source", score=99)],
        ),
        VideoItem(
            vod_id="tv_match",
            vod_name="Same Name Show",
            category=Category.TV,
            type_name="TV",
            vod_remarks="Updated to episode 10",
            sources=[_build_source("https://play.example.com/tv.m3u8", "tv_source", score=88)],
        ),
    ]

    dataset = hot_tv.build_hot_tv_dataset(feed_items, ranked_items, similarity_threshold=0.8)

    detail = dataset["details"][dataset["list"][0]["vod_id"]]
    assert detail["vod_id"] == "tv_match"
    assert detail["type_name"] == "TV"
    assert detail["source_count"] == 1
    assert "https://play.example.com/tv.m3u8" in detail["vod_play_url"]


def test_build_hot_tv_dataset_uses_feed_alt_titles_for_exact_match():
    hot_tv = _load_hot_tv_module()
    feed_items = [
        {
            "title": "Trending Alias",
            "alt_titles": ["Canonical Show"],
            "cover": "https://img.example.com/canonical-show.jpg",
        }
    ]
    ranked_items = [
        VideoItem(
            vod_id="tv_alias_match",
            vod_name="Canonical Show",
            category=Category.TV,
            type_name="TV",
            sources=[_build_source("https://play.example.com/canonical-show.m3u8", "alias_source")],
        )
    ]

    dataset = hot_tv.build_hot_tv_dataset(feed_items, ranked_items, similarity_threshold=0.95)

    assert [item["vod_id"] for item in dataset["list"]] == ["tv_alias_match"]
    detail = dataset["details"]["tv_alias_match"]
    assert detail["vod_name"] == "Canonical Show"
    assert "https://play.example.com/canonical-show.m3u8" in detail["vod_play_url"]


def test_build_hot_tv_dataset_formats_multi_source_lines():
    hot_tv = _load_hot_tv_module()
    feed_items = [{"title": "Multi Source Show"}]
    ranked_items = [
        VideoItem(
            vod_id="tv_multi_source",
            vod_name="Multi Source Show",
            category=Category.TV,
            type_name="TV",
            sources=[
                _build_source("https://play.example.com/source-a.m3u8", "storm", score=95),
                _build_source("https://play.example.com/source-b.m3u8", "ff", score=85),
            ],
        )
    ]

    dataset = hot_tv.build_hot_tv_dataset(feed_items, ranked_items, similarity_threshold=0.8)

    detail = dataset["details"]["tv_multi_source"]
    assert detail["vod_play_from"] == "storm·1080P$$$ff·1080P"
    assert detail["vod_play_url"] == (
        "Episode 1$https://play.example.com/source-a.m3u8"
        "$$$Episode 1$https://play.example.com/source-b.m3u8"
    )


def test_build_direct_hot_tv_dataset_uses_search_and_detail_fallback(monkeypatch):
    hot_tv = _load_hot_tv_module()
    feed_items = [
        {
            "title": "Hot Show A",
            "cover": "https://img.example.com/hot-show-a.jpg",
            "remarks": "Popular now",
        }
    ]
    client = _RoutingClient(
        routes={
            (
                "https://bfzyapi.com/api.php/provide/vod/",
                (("wd", "Hot Show A"),),
            ): _DummyResponse(
                {
                    "list": [
                        {
                            "vod_id": "bf-1",
                            "vod_name": "Hot Show A",
                            "vod_pic": "https://img.example.com/bf.jpg",
                            "vod_remarks": "BF search remarks",
                        }
                    ]
                }
            ),
            (
                "https://bfzyapi.com/api.php/provide/vod/",
                (("ac", "detail"), ("ids", "bf-1")),
            ): _DummyResponse(
                {
                    "list": [
                        {
                            "vod_id": "bf-1",
                            "vod_name": "Hot Show A",
                            "vod_pic": "https://img.example.com/bf.jpg",
                            "vod_remarks": "BF detail remarks",
                            "type_name": "TV",
                            "vod_play_from": "bfzy",
                            "vod_play_url": "Episode 1$https://play.example.com/bf-1.m3u8",
                        }
                    ]
                }
            ),
            (
                "https://cj.lziapi.com/api.php/provide/vod/",
                (("wd", "Hot Show A"),),
            ): _DummyResponse(
                {
                    "list": [
                        {
                            "vod_id": "lz-1",
                            "vod_name": "Hot Show A",
                            "vod_pic": "https://img.example.com/lz.jpg",
                            "vod_remarks": "LZ search remarks",
                        }
                    ]
                }
            ),
            (
                "https://cj.lziapi.com/api.php/provide/vod/",
                (("ac", "detail"), ("ids", "lz-1")),
            ): _DummyResponse(
                {
                    "list": [
                        {
                            "vod_id": "lz-1",
                            "vod_name": "Hot Show A",
                            "vod_pic": "https://img.example.com/lz.jpg",
                            "vod_remarks": "LZ detail remarks",
                            "type_name": "TV",
                            "vod_play_from": "lz",
                            "vod_play_url": "Episode 1$https://play.example.com/lz-1.m3u8",
                        }
                    ]
                }
            ),
        }
    )

    monkeypatch.setattr(hot_tv, "create_http_client", lambda timeout=10: client)
    monkeypatch.setattr(
        hot_tv,
        "DIRECT_HOT_TV_SOURCES",
        (
            ("bfzy", "https://bfzyapi.com/api.php/provide/vod/"),
            ("lz", "https://cj.lziapi.com/api.php/provide/vod/"),
        ),
    )

    dataset = hot_tv.build_direct_hot_tv_dataset(feed_items, similarity_threshold=0.95)

    assert [item["vod_name"] for item in dataset["list"]] == ["Hot Show A"]
    detail = dataset["details"][dataset["list"][0]["vod_id"]]
    assert detail["vod_name"] == "Hot Show A"
    assert detail["type_name"] == "TV"
    assert detail["source_count"] == 2
    assert detail["vod_play_from"] == "bfzy$$$lz"
    assert detail["vod_play_url"] == (
        "Episode 1$https://play.example.com/bf-1.m3u8"
        "$$$Episode 1$https://play.example.com/lz-1.m3u8"
    )
    assert dataset["list"][0]["vod_pic"] == "https://img.example.com/hot-show-a.jpg"
    assert dataset["list"][0]["vod_remarks"] == "Popular now"
    assert client.closed is True


def test_build_direct_hot_tv_dataset_returns_empty_on_search_failure(monkeypatch):
    hot_tv = _load_hot_tv_module()
    client = _RoutingClient(error=httpx.ConnectError("boom"))

    monkeypatch.setattr(hot_tv, "create_http_client", lambda timeout=10: client)
    monkeypatch.setattr(
        hot_tv,
        "DIRECT_HOT_TV_SOURCES",
        (("bfzy", "https://bfzyapi.com/api.php/provide/vod/"),),
    )

    dataset = hot_tv.build_direct_hot_tv_dataset(
        [{"title": "Hot Show A"}],
        similarity_threshold=0.95,
    )

    assert dataset["list"] == []
    assert dataset["details"] == {}
    assert isinstance(dataset["update_time"], str)
    assert client.closed is True
