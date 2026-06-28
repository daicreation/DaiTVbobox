import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.builder import build_all_outputs, _build_tvbox_json, _dedup_and_merge, _limit_sources, _tag_platform
from src.constants import OUTPUT_HOT_TV_JSON
from src.models import Category, PlaySource, Quality, VideoItem


@pytest.fixture(autouse=True)
def stub_homepage_feeds(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.builder.fetch_hot_tv_feed", lambda: [])
    monkeypatch.setattr("src.builder.fetch_hot_variety_feed", lambda: [])


class TestDedupAndMerge:
    def test_identical_titles_merge_sources(self):
        src1 = PlaySource(url="url1", source_name="A", quality=Quality.K4, score=90, is_available=True)
        src2 = PlaySource(url="url2", source_name="B", quality=Quality.K1080, score=80, is_available=True)

        item1 = VideoItem(vod_id="1", vod_name="Example Movie", sources=[src1])
        item2 = VideoItem(vod_id="2", vod_name="Example Movie", sources=[src2])

        merged = _dedup_and_merge([item1, item2], 0.80, 10)

        assert len(merged) == 1
        assert len(merged[0].sources) == 2


class TestLimitSources:
    def test_source_limit_is_enforced(self):
        sources = [
            PlaySource(url=f"url{i}", source_name=f"S{i}", quality=Quality.K1080, score=100 - i, is_available=True)
            for i in range(8)
        ]

        result = _limit_sources(sources, 5)

        assert len(result) == 5


class TestTagPlatform:
    def test_platform_is_detected_from_text(self):
        item = VideoItem(
            vod_id="1",
            vod_name="Example Drama",
            vod_remarks="Updated on iQIYI",
            sources=[PlaySource(url="url", source_name="Mirror", quality=Quality.K1080, score=80, is_available=True)],
        )
        platform_map = {
            "iqiyi": {"name": "iQIYI", "keywords": ["iqiyi", "爱奇艺"]},
        }

        _tag_platform(item, platform_map)

        assert item.platform == "iQIYI"


class TestBuildTvboxJson:
    def test_basic_shape(self):
        src = PlaySource(
            url="https://example.com/play/1",
            source_name="SourceA",
            quality=Quality.K4,
            score=90,
            is_available=True,
            episode_name="Episode 1",
        )
        item = VideoItem(vod_id="test_001", vod_name="Example Movie", vod_year="2025", sources=[src])

        result = _build_tvbox_json([item], "movie", "2025-06-24 08:00:00", 10)

        assert "class" in result
        assert "filters" in result
        assert "list" in result
        assert result["total"] == 1
        assert result["page"] == 1


class TestBuildAllOutputs:
    def test_does_not_append_discovered_sites_to_config(self):
        discovered_site = VideoItem(
            vod_id="site_good",
            vod_name="[站點] 星河影院",
            type_name="站點",
            sources=[
                PlaySource(
                    url="https://good.example.com/api.php/provide/vod/",
                    source_name="TestSource",
                    quality=Quality.K1080,
                    score=80,
                    is_available=True,
                )
            ],
        )

        paths = build_all_outputs(
            {"movie": [discovered_site], "tv": [], "variety": [], "live": []},
            {"output": {"max_sources_per_video": 10, "max_items_per_category": 100}},
            "https://tv.example.com",
        )

        with open(paths["config"], "r", encoding="utf-8") as f:
            config = json.load(f)

        site_names = {site["name"] for site in config["sites"]}

        assert "星河影院" not in site_names
        assert all(not site["key"].startswith("auto_") for site in config["sites"])

    def test_shared_config_keeps_only_curated_sites(self):
        paths = build_all_outputs(
            {"movie": [], "tv": [], "variety": [], "live": []},
            {"output": {"max_sources_per_video": 10, "max_items_per_category": 100}},
            "https://tv.example.com",
        )

        with open(paths["config"], "r", encoding="utf-8") as f:
            config_root = json.load(f)

        site_keys = [site["key"] for site in config_root["sites"]]
        assert site_keys == ["chill", "bfzy", "ff", "sn", "lz", "360", "js", "jy", "yh", "md", "ik", "wj", "ry"]

    def test_ruyi_is_last_backup_source(self):
        paths = build_all_outputs(
            {"movie": [], "tv": [], "variety": [], "live": []},
            {"output": {"max_sources_per_video": 10, "max_items_per_category": 100}},
            "https://tv.example.com",
        )

        with open(paths["config"], "r", encoding="utf-8") as f:
            config_root = json.load(f)

        assert config_root["sites"][-1]["key"] == "ry"
        assert config_root["sites"][-1]["api"] == "https://tv.example.com/p/ry"

    def test_generates_hk_and_cn_configs_with_same_sites(self):
        paths = build_all_outputs(
            {"movie": [], "tv": [], "variety": [], "live": []},
            {"output": {"max_sources_per_video": 10, "max_items_per_category": 100}},
            "https://tv.example.com",
        )

        with open(paths["config"], "r", encoding="utf-8") as f:
            config_root = json.load(f)
        with open(paths["config_hk"], "r", encoding="utf-8") as f:
            config_hk = json.load(f)
        with open(paths["config_cn"], "r", encoding="utf-8") as f:
            config_cn = json.load(f)

        assert paths["config_hk"].name == "config.hk.json"
        assert paths["config_cn"].name == "config.cn.json"
        assert config_root["sites"] == config_hk["sites"] == config_cn["sites"]
        assert config_root["sites"][0]["api"] == "https://tv.example.com/api"

    def test_generates_empty_hot_tv_shape(self):
        tv_item = VideoItem(
            vod_id="tv_001",
            vod_name="Example TV Show",
            type_name="TV",
            category=Category.TV,
            vod_remarks="Updated to episode 8",
            episode_updated=8,
            sources=[
                PlaySource(
                    url="https://example.com/tv-001.m3u8",
                    source_name="A",
                    quality=Quality.K1080,
                    score=88,
                    is_available=True,
                )
            ],
        )

        paths = build_all_outputs(
            {"movie": [], "tv": [tv_item], "variety": [], "live": []},
            {
                "output": {"max_sources_per_video": 10, "max_items_per_category": 100},
                "dedup": {"title_similarity_threshold": 0.8},
            },
            "https://tv.example.com",
        )

        assert paths["hot_tv"] == OUTPUT_HOT_TV_JSON

        with open(paths["hot_tv"], "r", encoding="utf-8") as f:
            hot_tv_data = json.load(f)

        assert set(hot_tv_data) == {"list", "details", "update_time"}
        assert hot_tv_data["list"] == []
        assert hot_tv_data["details"] == {}

    def test_rewrites_hot_tv_covers_to_worker_proxy(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("src.builder.fetch_hot_tv_feed", lambda: [{"title": "Hot Show A", "cover": "https://img.example.com/poster.jpg"}])

        def fake_build_hot_tv_dataset(feed_items, ranked_tv_items, similarity_threshold):
            return {
                "list": [
                    {
                        "vod_id": "tv_001",
                        "vod_name": "Hot Show A",
                        "vod_pic": "https://img.example.com/poster.jpg",
                        "source_count": 1,
                    }
                ],
                "details": {
                    "tv_001": {
                        "vod_id": "tv_001",
                        "vod_name": "Hot Show A",
                        "vod_pic": "https://img.example.com/poster.jpg",
                        "source_count": 1,
                        "vod_play_from": "bfzy",
                        "vod_play_url": "Episode 1$https://play.example.com/tv-001.m3u8",
                    }
                },
                "update_time": "2026-06-26 02:00:00",
            }

        monkeypatch.setattr("src.builder.build_hot_tv_dataset", fake_build_hot_tv_dataset)

        paths = build_all_outputs(
            {"movie": [], "tv": [], "variety": [], "live": []},
            {
                "output": {"max_sources_per_video": 10, "max_items_per_category": 100},
                "dedup": {"title_similarity_threshold": 0.8},
            },
            "https://tv.example.com",
        )

        with open(paths["hot_tv"], "r", encoding="utf-8") as f:
            hot_tv_data = json.load(f)

        expected = "https://tv.example.com/img?url=https%3A%2F%2Fimg.example.com%2Fposter.jpg"
        assert hot_tv_data["list"][0]["vod_pic"] == expected
        assert hot_tv_data["details"]["tv_001"]["vod_pic"] == expected
