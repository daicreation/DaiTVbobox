# ============================================================
# TVBox 影視聚合系統 — 整合測試
# 測試完整的 pipeline 流程
# ============================================================

import sys
import json
import pickle
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import (
    VideoItem,
    PlaySource,
    Quality,
    Category,
    SourceCache,
)
from src.ranker import rank_all_items
from src.builder import build_all_outputs


# ---- 測試數據 ----
def _create_mock_source_caches() -> dict[str, SourceCache]:
    """建立模擬的來源快取數據"""
    sources = {}

    # 飯太硬
    fantaiying_items = [
        VideoItem(
            vod_id="movie_001",
            vod_name="測試電影A (2025)",
            vod_pic="https://img.example.com/a.jpg",
            vod_remarks="4K·飯太硬",
            type_name="動作",
            vod_year="2025",
            vod_area="美國",
            vod_actor="演員1",
            category=Category.MOVIE,
            sources=[
                PlaySource(
                    url="https://example.com/play/movie_a_4k",
                    source_name="飯太硬",
                    quality=Quality.K4,
                    response_time=1.2,
                    is_available=True,
                    stability=85.0,
                    score=90.0,
                ),
            ],
        ),
    ]
    sources["fantaiying"] = SourceCache(
        source_key="fantaiying",
        source_name="飯太硬",
        fetched_at="2025-06-24T00:00:00Z",
        item_count=len(fantaiying_items),
        items=[_item_to_dict(it) for it in fantaiying_items],
    )

    # 肥貓 (同一部電影，不同來源)
    feimao_items = [
        VideoItem(
            vod_id="movie_002",
            vod_name="測試電影A",
            vod_pic="https://img.example.com/a2.jpg",
            vod_remarks="1080P·肥貓",
            type_name="動作",
            vod_year="2025",
            vod_area="美國",
            category=Category.MOVIE,
            sources=[
                PlaySource(
                    url="https://example.com/play/movie_a_1080",
                    source_name="肥貓",
                    quality=Quality.K1080,
                    response_time=2.5,
                    is_available=True,
                    stability=70.0,
                    score=75.0,
                ),
            ],
        ),
    ]
    sources["feimao"] = SourceCache(
        source_key="feimao",
        source_name="肥貓",
        fetched_at="2025-06-24T00:00:01Z",
        item_count=len(feimao_items),
        items=[_item_to_dict(it) for it in feimao_items],
    )

    return sources


def _item_to_dict(item: VideoItem) -> dict:
    """VideoItem → dict (從 source_fetcher 複製)"""
    return {
        "vod_id": item.vod_id,
        "vod_name": item.vod_name,
        "vod_pic": item.vod_pic,
        "vod_remarks": item.vod_remarks,
        "type_name": item.type_name,
        "vod_year": item.vod_year,
        "vod_area": item.vod_area,
        "vod_actor": item.vod_actor,
        "vod_director": item.vod_director,
        "vod_content": item.vod_content,
        "vod_score": item.vod_score,
        "category": item.category.value,
        "platform": item.platform,
        "episode_count": item.episode_count,
        "episode_updated": item.episode_updated,
        "sources": [
            {
                "url": s.url,
                "source_name": s.source_name,
                "quality": s.quality.value,
                "episode_name": s.episode_name,
                "is_available": s.is_available,
                "response_time": s.response_time,
                "stability": s.stability,
                "score": s.score,
                "http_status": s.http_status,
            }
            for s in item.sources
        ],
    }


def _dict_to_item(raw: dict) -> VideoItem:
    """dict → VideoItem (從 health_checker 複製)"""
    sources = []
    for src_dict in raw.get("sources", []):
        sources.append(PlaySource(
            url=src_dict.get("url", ""),
            source_name=src_dict.get("source_name", ""),
            quality=Quality.from_string(src_dict.get("quality", "")),
            episode_name=src_dict.get("episode_name", "第1集"),
            # 恢復健康檢查數據
            is_available=src_dict.get("is_available", True),
            response_time=src_dict.get("response_time", 0.0),
            stability=src_dict.get("stability", 0.0),
            score=src_dict.get("score", 0.0),
            http_status=src_dict.get("http_status", 200),
        ))
    return VideoItem(
        vod_id=raw.get("vod_id", ""),
        vod_name=raw.get("vod_name", ""),
        vod_pic=raw.get("vod_pic", ""),
        vod_remarks=raw.get("vod_remarks", ""),
        type_name=raw.get("type_name", ""),
        vod_year=str(raw.get("vod_year", "")),
        vod_area=raw.get("vod_area", ""),
        vod_actor=raw.get("vod_actor", ""),
        vod_director=raw.get("vod_director", ""),
        vod_content=raw.get("vod_content", ""),
        vod_score=str(raw.get("vod_score", "")),
        category=Category.from_string(raw.get("category", "movie")),
        platform=raw.get("platform", ""),
        episode_count=raw.get("episode_count", 0),
        episode_updated=raw.get("episode_updated", 0),
        sources=sources,
    )


class TestIntegrationPipeline:
    """
    完整 Pipeline 整合測試

    source_fetcher → health_checker → ranker → builder
    (health_checker 部分使用預先填入的測試數據)
    """

    # 完整的評分規則
    MOCK_RULES = {
        "scoring": {
            "weights": {
                "speed": 0.25,
                "success_rate": 0.30,
                "stability": 0.25,
                "quality": 0.20,
            },
            "quality_bonus": {
                "4K": 100, "1080P": 70, "720P": 40, "480P": 10, "未知": 0,
            },
        },
        "thresholds": {
            "min_score": 50,
            "min_success_rate": 0.7,
            "max_response_time": 10.0,
            "min_sources_per_video": 1,
        },
        "dedup": {
            "title_similarity_threshold": 0.80,
            "use_levenshtein": True,
            "normalize_title": True,
        },
        "output": {
            "max_items_per_category": 5000,
            "max_sources_per_video": 10,
            "compress_json": False,
            "update_time_format": "%Y-%m-%d %H:%M:%S",
        },
        "ranking": {
            "order": ["quality", "score", "year", "source_count"],
        },
        "platform_keywords": {
            "iqiyi": {"name": "愛奇藝", "keywords": ["iqiyi", "愛奇藝"]},
            "tencent": {"name": "騰訊", "keywords": ["tencent", "騰訊"]},
        },
    }

    def test_full_pipeline(self, tmp_path):
        """完整流程測試: fetch → check → rank → build"""
        # ---- 模擬 source_fetcher 輸出 ----
        source_caches = _create_mock_source_caches()

        # ---- 模擬 health_checker: 從快取重建 VideoItem 列表 ----
        all_items = {"movie": [], "tv": [], "variety": [], "live": []}
        for cache in source_caches.values():
            for raw_item in cache.items:
                item = _dict_to_item(raw_item)
                all_items["movie"].append(item)

        # 驗證 health_checker 階段
        assert len(all_items["movie"]) == 2  # 兩條來自不同源的相同電影

        # ---- 執行 ranker ----
        ranked = rank_all_items(all_items, self.MOCK_RULES)

        # 驗證 ranker 結果
        assert "movie" in ranked
        assert len(ranked["movie"]) >= 1

        # 每個來源應有評分
        for item in ranked["movie"]:
            for src in item.sources:
                assert src.score > 0

        # ---- 執行 builder ----
        paths = build_all_outputs(ranked, self.MOCK_RULES, "https://tv.xxx.com")

        # 驗證 builder 輸出
        assert "movie" in paths
        assert paths["movie"].exists()

        # 驗證 JSON 格式
        with open(paths["movie"], "r", encoding="utf-8") as f:
            movie_data = json.load(f)

        assert "class" in movie_data
        assert "list" in movie_data
        assert "total" in movie_data
        assert movie_data["total"] >= 1  # 合併後應為 1 部電影

        # 驗證合併後的來源
        movie_list = movie_data["list"]
        assert len(movie_list) >= 1

        merged_movie = movie_list[0]
        # 合併後應有來自飯太硬和肥貓的兩個來源
        assert merged_movie["source_count"] >= 2

        # 驗證 config.json 也存在
        assert "config" in paths
        assert paths["config"].exists()

        print(f"\n整合測試通過!")
        print(f"  電影數量: {movie_data['total']}")
        print(f"  合併後來源數: {merged_movie['source_count']}")
        print(f"  最佳畫質: {merged_movie.get('vod_quality', 'N/A')}")
