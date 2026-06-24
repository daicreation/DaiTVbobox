# ============================================================
# TVBox 影視聚合系統 — 評分排序測試
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ranker import (
    rank_all_items,
    _calculate_source_score,
    _item_sort_key,
)
from src.models import (
    VideoItem,
    PlaySource,
    Quality,
)


class TestCalculateSourceScore:
    """測試來源評分計算"""

    def test_high_quality_fast(self):
        """高畫質 + 快速 = 高分"""
        src = PlaySource(
            url="https://example.com/play",
            source_name="測試源",
            quality=Quality.K4,
            response_time=0.5,
            is_available=True,
            stability=90.0,
        )
        weights = {"speed": 0.25, "success_rate": 0.30, "stability": 0.25, "quality": 0.20}
        quality_bonus = {"4K": 100, "1080P": 70, "720P": 40, "480P": 10, "未知": 0}

        score = _calculate_source_score(src, weights, quality_bonus)

        # 應為高分 (>85)
        assert score > 80.0, f"Expected > 80, got {score}"

    def test_unavailable(self):
        """不可用來源"""
        src = PlaySource(
            url="https://example.com/play",
            source_name="測試源",
            quality=Quality.K4,
            response_time=10.0,
            is_available=False,
            stability=0.0,
        )
        weights = {"speed": 0.25, "success_rate": 0.30, "stability": 0.25, "quality": 0.20}
        quality_bonus = {"4K": 100, "1080P": 70, "720P": 40, "480P": 10, "未知": 0}

        score = _calculate_source_score(src, weights, quality_bonus)

        # 不可用 = 成功率 0 分 + 穩定性 0 分 = 即使有畫質加分，總分也應很低
        assert score < 60.0, f"Expected < 60, got {score}"

    def test_low_quality_slow(self):
        """低畫質 + 慢速 = 低分"""
        src = PlaySource(
            url="https://example.com/play",
            source_name="測試源",
            quality=Quality.K480,
            response_time=8.0,
            is_available=True,
            stability=30.0,
        )
        weights = {"speed": 0.25, "success_rate": 0.30, "stability": 0.25, "quality": 0.20}
        quality_bonus = {"4K": 100, "1080P": 70, "720P": 40, "480P": 10, "未知": 0}

        score = _calculate_source_score(src, weights, quality_bonus)

        # 應為低分 (<50)
        assert score < 50.0, f"Expected < 50, got {score}"


class TestItemSortKey:
    """測試影片排序鍵"""

    def test_4k_first(self):
        """4K 優先"""
        item_4k = VideoItem(
            vod_id="4k",
            vod_name="4K 電影",
            vod_year="2025",
            sources=[
                PlaySource(url="url", source_name="A", quality=Quality.K4, score=80, is_available=True)
            ],
        )
        item_1080 = VideoItem(
            vod_id="1080",
            vod_name="1080P 電影",
            vod_year="2025",
            sources=[
                PlaySource(url="url", source_name="A", quality=Quality.K1080, score=90, is_available=True)
            ],
        )

        order = ["quality", "score", "year", "source_count"]
        key_4k = _item_sort_key(item_4k, order)
        key_1080 = _item_sort_key(item_1080, order)

        # 4K 應該排在 1080P 前面 (以 quality 為第一排序維度時)
        assert key_4k[0] > key_1080[0]  # quality: 4K=4 > 1080P=3


class TestRankAllItems:
    """測試完整評分流程"""

    def test_basic_ranking(self):
        """基本評分排序"""
        src_4k = PlaySource(
            url="https://example.com/4k",
            source_name="飯太硬",
            quality=Quality.K4,
            response_time=1.0,
            is_available=True,
            stability=85.0,
        )
        src_1080 = PlaySource(
            url="https://example.com/1080",
            source_name="肥貓",
            quality=Quality.K1080,
            response_time=2.0,
            is_available=True,
            stability=70.0,
        )

        item = VideoItem(
            vod_id="test_001",
            vod_name="測試電影",
            vod_year="2025",
            sources=[src_4k, src_1080],
        )

        rules = {
            "scoring": {
                "weights": {"speed": 0.25, "success_rate": 0.30, "stability": 0.25, "quality": 0.20},
                "quality_bonus": {"4K": 100, "1080P": 70, "720P": 40, "480P": 10, "未知": 0},
            },
            "thresholds": {"min_score": 50},
            "ranking": {"order": ["quality", "score", "year", "source_count"]},
        }

        all_items = {"movie": [item]}
        ranked = rank_all_items(all_items, rules)

        ranked_item = ranked["movie"][0]
        # 4K 來源應排在前面 (更高分)
        assert ranked_item.sources[0].quality == Quality.K4
        assert ranked_item.sources[0].score > ranked_item.sources[1].score
