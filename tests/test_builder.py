# ============================================================
# TVBox 影視聚合系統 — JSON 生成器測試
# ============================================================

import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.builder import (
    build_all_outputs,
    _dedup_and_merge,
    _limit_sources,
    _tag_platform,
    _build_tvbox_json,
)
from src.constants import OUTPUT_HOT_TV_JSON
from src.models import (
    VideoItem,
    PlaySource,
    Quality,
    Category,
)


class TestDedupAndMerge:
    """測試去重合併"""

    def test_identical_titles(self):
        """相同標題合併"""
        src1 = PlaySource(url="url1", source_name="A", quality=Quality.K4, score=90, is_available=True)
        src2 = PlaySource(url="url2", source_name="B", quality=Quality.K1080, score=80, is_available=True)

        item1 = VideoItem(vod_id="1", vod_name="測試電影", sources=[src1])
        item2 = VideoItem(vod_id="2", vod_name="測試電影", sources=[src2])

        merged = _dedup_and_merge([item1, item2], 0.80, 10)

        # 應合併為 1 個影片
        assert len(merged) == 1
        # 合併後應有 2 個來源
        assert len(merged[0].sources) == 2

    def test_different_titles(self):
        """不同標題不合併"""
        src1 = PlaySource(url="url1", source_name="A", quality=Quality.K4, score=90, is_available=True)
        src2 = PlaySource(url="url2", source_name="B", quality=Quality.K1080, score=80, is_available=True)

        # 使用完全不同的標題確保 Levenshtein 相似度 < 0.80
        item1 = VideoItem(vod_id="1", vod_name="星際大戰", sources=[src1])
        item2 = VideoItem(vod_id="2", vod_name="海底總動員", sources=[src2])

        merged = _dedup_and_merge([item1, item2], 0.80, 10)

        # 不應合併
        assert len(merged) == 2

    def test_near_duplicate_titles(self):
        """近似標題 (Levenshtein 匹配)"""
        src1 = PlaySource(url="url1", source_name="A", quality=Quality.K4, score=90, is_available=True)
        src2 = PlaySource(url="url2", source_name="B", quality=Quality.K1080, score=80, is_available=True)

        # 同一個電影，只是名稱略有不同
        item1 = VideoItem(vod_id="1", vod_name="範例電影 (2025)", sources=[src1])
        item2 = VideoItem(vod_id="2", vod_name="範例電影 HD", sources=[src2])

        merged = _dedup_and_merge([item1, item2], 0.80, 10)

        # normalize_title 會去除 (2025) 和 HD → "範例電影" → 應合併
        assert len(merged) == 1


class TestLimitSources:
    """測試來源數量限制"""

    def test_within_limit(self):
        """未超過限制"""
        sources = [
            PlaySource(url=f"url{i}", source_name=f"S{i}", quality=Quality.K1080, score=80, is_available=True)
            for i in range(5)
        ]
        result = _limit_sources(sources, 10)
        assert len(result) == 5

    def test_exceed_limit(self):
        """超過限制"""
        sources = [
            PlaySource(url=f"url{i}", source_name=f"S{i % 3}", quality=Quality.K1080, score=80 - i, is_available=True)
            for i in range(20)
        ]
        result = _limit_sources(sources, 5)
        assert len(result) == 5


class TestTagPlatform:
    """測試平台標記"""

    def test_iqiyi_detection(self):
        """檢測愛奇藝"""
        item = VideoItem(
            vod_id="1",
            vod_name="測試劇集",
            vod_remarks="更新至24集·愛奇藝",
            sources=[
                PlaySource(url="url", source_name="愛奇藝源", quality=Quality.K1080, score=80, is_available=True)
            ],
        )
        platform_map = {
            "iqiyi": {"name": "愛奇藝", "keywords": ["iqiyi", "愛奇藝"]},
        }
        _tag_platform(item, platform_map)
        assert item.platform == "愛奇藝"


class TestBuildTvboxJson:
    """測試 TVBox JSON 生成"""

    def test_basic_structure(self):
        """基本結構檢查"""
        src = PlaySource(
            url="https://example.com/play/1",
            source_name="飯太硬",
            quality=Quality.K4,
            score=90,
            is_available=True,
            episode_name="第1集",
        )
        item = VideoItem(
            vod_id="test_001",
            vod_name="測試電影",
            vod_year="2025",
            sources=[src],
        )

        result = _build_tvbox_json([item], "movie", "2025-06-24 08:00:00", 10)

        assert "class" in result
        assert "filters" in result
        assert "list" in result
        assert result["total"] == 1
        assert result["page"] == 1
        assert len(result["list"]) == 1


class TestBuildAllOutputs:
    """測試完整輸出與清洗規則"""

    def test_filters_adult_and_script_sites(self):
        """配置輸出應過濾采集/腳本型站點"""
        good_site = VideoItem(
            vod_id="site_good",
            vod_name="[站點] 星河影院",
            type_name="站點",
            sources=[
                PlaySource(
                    url="https://good.example.com/api.php/provide/vod/",
                    source_name="測試源",
                    quality=Quality.K1080,
                    score=80,
                    is_available=True,
                )
            ],
        )
        bad_collect = VideoItem(
            vod_id="site_bad_collect",
            vod_name="[站點] 🦔暴風┃采集",
            type_name="站點",
            sources=[
                PlaySource(
                    url="https://bfzyapi.com/api.php/provide/vod",
                    source_name="測試源",
                    quality=Quality.K1080,
                    score=80,
                    is_available=True,
                )
            ],
        )
        bad_script = VideoItem(
            vod_id="site_bad_script",
            vod_name="[站點] 猫头鹰｜秒播",
            type_name="站點",
            sources=[
                PlaySource(
                    url="https://gitee.com/monosodium-glutamate/wjwj/raw/master/lib/get.js",
                    source_name="測試源",
                    quality=Quality.K1080,
                    score=80,
                    is_available=True,
                )
            ],
        )

        paths = build_all_outputs(
            {"movie": [good_site, bad_collect, bad_script], "tv": [], "variety": [], "live": []},
            {"output": {"max_sources_per_video": 10, "max_items_per_category": 100}},
            "https://tv.example.com",
        )

        with open(paths["config"], "r", encoding="utf-8") as f:
            config = json.load(f)

        names = {site["name"] for site in config["sites"]}
        assert "星河影院" in names
        assert "🦔暴風┃采集" not in names
        assert "猫头鹰｜秒播" not in names

    def test_excludes_config_source_entries(self):
        """多倉配置源本身不應直接出現在最終站點列表"""
        paths = build_all_outputs(
            {"movie": [], "tv": [], "variety": [], "live": []},
            {"output": {"max_sources_per_video": 10, "max_items_per_category": 100}},
            "https://tv.example.com",
        )

        with open(paths["config"], "r", encoding="utf-8") as f:
            config = json.load(f)

        names = {site["name"] for site in config["sites"]}
        assert "💨 瀟灑" not in names
        assert "🍎 小蘋果" not in names
        assert "🐟 摸魚兒" not in names
        assert "🍚 飯太硬" not in names

    def test_recategorizes_tv_and_variety_outputs(self):
        """錯分到 movie 的內容應在輸出時重新分類"""
        tv_item = VideoItem(
            vod_id="tv_001",
            vod_name="測試劇集",
            vod_remarks="更新至24集",
            type_name="劇集",
            category=Category.MOVIE,
            sources=[
                PlaySource(
                    url="https://example.com/tv.m3u8",
                    source_name="A",
                    quality=Quality.K1080,
                    score=88,
                    is_available=True,
                )
            ],
        )
        variety_item = VideoItem(
            vod_id="variety_001",
            vod_name="快樂綜藝",
            vod_remarks="2026",
            type_name="綜藝",
            category=Category.MOVIE,
            sources=[
                PlaySource(
                    url="https://example.com/variety.m3u8",
                    source_name="B",
                    quality=Quality.K1080,
                    score=82,
                    is_available=True,
                )
            ],
        )

        paths = build_all_outputs(
            {"movie": [tv_item, variety_item], "tv": [], "variety": [], "live": []},
            {"output": {"max_sources_per_video": 10, "max_items_per_category": 100}},
            "https://tv.example.com",
        )

        with open(paths["tv"], "r", encoding="utf-8") as f:
            tv_data = json.load(f)
        with open(paths["variety"], "r", encoding="utf-8") as f:
            variety_data = json.load(f)

        assert tv_data["total"] == 1
        assert tv_data["list"][0]["vod_name"] == "測試劇集"
        assert variety_data["total"] == 1
        assert variety_data["list"][0]["vod_name"] == "快樂綜藝"

    def test_generates_hk_and_cn_configs(self):
        """應同時輸出香港版與內地版配置"""
        paths = build_all_outputs(
            {"movie": [], "tv": [], "variety": [], "live": []},
            {"output": {"max_sources_per_video": 10, "max_items_per_category": 100}},
            "https://tv.example.com",
        )

        assert "config_hk" in paths
        assert "config_cn" in paths
        assert paths["config_hk"].name == "config.hk.json"
        assert paths["config_cn"].name == "config.cn.json"

        with open(paths["config"], "r", encoding="utf-8") as f:
            config_root = json.load(f)
        with open(paths["config_hk"], "r", encoding="utf-8") as f:
            config_hk = json.load(f)
        with open(paths["config_cn"], "r", encoding="utf-8") as f:
            config_cn = json.load(f)

        assert config_root["sites"][0]["api"] == "https://tv.example.com/api"
        assert config_hk["sites"][0]["api"] == "https://tv.example.com/api"
        assert config_cn["sites"][0]["api"] == "https://tv.example.com/api"
        assert config_root["sites"] == config_hk["sites"] == config_cn["sites"]

    def test_regional_configs_use_shared_proxy_paths(self):
        """核心直連站點應共用根路徑代理"""
        paths = build_all_outputs(
            {"movie": [], "tv": [], "variety": [], "live": []},
            {"output": {"max_sources_per_video": 10, "max_items_per_category": 100}},
            "https://tv.example.com",
        )

        with open(paths["config_hk"], "r", encoding="utf-8") as f:
            config_hk = json.load(f)
        with open(paths["config_cn"], "r", encoding="utf-8") as f:
            config_cn = json.load(f)

        hk_sites = {site["key"]: site["api"] for site in config_hk["sites"]}
        cn_sites = {site["key"]: site["api"] for site in config_cn["sites"]}

        assert hk_sites["bfzy"] == "https://tv.example.com/p/bfzy"
        assert cn_sites["bfzy"] == "https://tv.example.com/p/bfzy"
        assert hk_sites["360"] == "https://tv.example.com/p/360"
        assert cn_sites["360"] == "https://tv.example.com/p/360"

    def test_shared_config_keeps_only_direct_core_sites(self):
        paths = build_all_outputs(
            {"movie": [], "tv": [], "variety": [], "live": []},
            {"output": {"max_sources_per_video": 10, "max_items_per_category": 100}},
            "https://tv.example.com",
        )

        with open(paths["config"], "r", encoding="utf-8") as f:
            config_root = json.load(f)

        site_keys = [site["key"] for site in config_root["sites"]]
        assert site_keys == ["chill", "bfzy", "ff", "sn", "lz", "360", "js", "jy", "yh", "md", "ik", "wj"]

    def test_config_still_keeps_chill_tv_first(self):
        paths = build_all_outputs(
            {"movie": [], "tv": [], "variety": [], "live": []},
            {"output": {"max_sources_per_video": 10, "max_items_per_category": 100}},
            "https://tv.example.com",
        )

        with open(paths["config"], "r", encoding="utf-8") as f:
            config_root = json.load(f)

        assert config_root["sites"][0]["key"] == "chill"
        assert "Chill-TV" in config_root["sites"][0]["name"]

    def test_generates_hot_tv_output_with_real_empty_feed_shape(self, monkeypatch: pytest.MonkeyPatch):
        def fake_fetch_hot_tv_feed():
            return []

        monkeypatch.setattr("src.builder.fetch_hot_tv_feed", fake_fetch_hot_tv_feed)

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
        assert paths["hot_tv"].name == "hot_tv.json"

        with open(paths["hot_tv"], "r", encoding="utf-8") as f:
            hot_tv_data = json.load(f)

        assert set(hot_tv_data) == {"list", "details", "update_time"}
        assert hot_tv_data["list"] == []
        assert hot_tv_data["details"] == {}
        assert isinstance(hot_tv_data["update_time"], str)
        assert hot_tv_data["update_time"]

    def test_passes_ranked_tv_items_into_hot_tv_builder(self, monkeypatch: pytest.MonkeyPatch):
        captured = {}

        def fake_fetch_hot_tv_feed():
            return []

        def fake_build_hot_tv_dataset(feed_items, ranked_tv_items, similarity_threshold):
            captured["feed_items"] = feed_items
            captured["ranked_tv_items"] = ranked_tv_items
            captured["similarity_threshold"] = similarity_threshold
            return {
                "list": [],
                "details": {},
                "update_time": "2026-06-26 00:00:00",
            }

        monkeypatch.setattr("src.builder.fetch_hot_tv_feed", fake_fetch_hot_tv_feed)
        monkeypatch.setattr("src.builder.build_hot_tv_dataset", fake_build_hot_tv_dataset)

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
        assert paths["hot_tv"].name == "hot_tv.json"
        assert [item.vod_id for item in captured["ranked_tv_items"]] == ["tv_001"]
        assert captured["feed_items"] == []
        assert captured["similarity_threshold"] == 0.8

        with open(paths["hot_tv"], "r", encoding="utf-8") as f:
            hot_tv_data = json.load(f)

        assert hot_tv_data == {
            "list": [],
            "details": {},
            "update_time": "2026-06-26 00:00:00",
        }

    def test_uses_direct_hot_tv_fallback_when_ranked_path_is_empty(self, monkeypatch: pytest.MonkeyPatch):
        captured = {}

        def fake_fetch_hot_tv_feed():
            return [{"title": "Hot Show A", "cover": "https://img.example.com/hot.jpg"}]

        def fake_build_hot_tv_dataset(feed_items, ranked_tv_items, similarity_threshold):
            captured["primary_feed_items"] = feed_items
            captured["primary_ranked_tv_items"] = ranked_tv_items
            captured["primary_similarity_threshold"] = similarity_threshold
            return {
                "list": [],
                "details": {},
                "update_time": "2026-06-26 00:00:00",
            }

        def fake_build_direct_hot_tv_dataset(feed_items, similarity_threshold):
            captured["fallback_feed_items"] = feed_items
            captured["fallback_similarity_threshold"] = similarity_threshold
            return {
                "list": [{"vod_id": "bf-1", "vod_name": "Hot Show A", "source_count": 1}],
                "details": {
                    "bf-1": {
                        "vod_id": "bf-1",
                        "vod_name": "Hot Show A",
                        "source_count": 1,
                        "vod_play_from": "bfzy",
                        "vod_play_url": "Episode 1$https://play.example.com/bf-1.m3u8",
                    }
                },
                "update_time": "2026-06-26 01:00:00",
            }

        monkeypatch.setattr("src.builder.fetch_hot_tv_feed", fake_fetch_hot_tv_feed)
        monkeypatch.setattr("src.builder.build_hot_tv_dataset", fake_build_hot_tv_dataset)
        monkeypatch.setattr("src.builder.build_direct_hot_tv_dataset", fake_build_direct_hot_tv_dataset)

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

        assert captured["primary_feed_items"] == [{"title": "Hot Show A", "cover": "https://img.example.com/hot.jpg"}]
        assert [item.vod_id for item in captured["primary_ranked_tv_items"]] == ["tv_001"]
        assert captured["fallback_feed_items"] == [{"title": "Hot Show A", "cover": "https://img.example.com/hot.jpg"}]
        assert captured["fallback_similarity_threshold"] == 0.8

        with open(paths["hot_tv"], "r", encoding="utf-8") as f:
            hot_tv_data = json.load(f)

        assert hot_tv_data["list"] == [{"vod_id": "bf-1", "vod_name": "Hot Show A", "source_count": 1}]
        assert hot_tv_data["details"]["bf-1"]["vod_play_from"] == "bfzy"
