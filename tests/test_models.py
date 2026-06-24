# ============================================================
# TVBox 影視聚合系統 — 數據模型測試
# ============================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import (
    Quality,
    Category,
    PlaySource,
    VideoItem,
    HealthCheckResult,
    SourceCache,
)


class TestQuality:
    """測試畫質枚舉"""

    def test_from_string_4k(self):
        """4K 解析"""
        assert Quality.from_string("4K") == Quality.K4
        assert Quality.from_string("2160P") == Quality.K4
        assert Quality.from_string("UHD") == Quality.K4

    def test_from_string_1080p(self):
        """1080P 解析"""
        assert Quality.from_string("1080P") == Quality.K1080
        assert Quality.from_string("FHD") == Quality.K1080
        assert Quality.from_string("BLURAY") == Quality.K1080

    def test_from_string_unknown(self):
        """未知畫質"""
        assert Quality.from_string("XYZ") == Quality.UNKNOWN
        assert Quality.from_string("") == Quality.UNKNOWN

    def test_sort_order(self):
        """排序順序"""
        assert Quality.K4.sort_order() < Quality.K1080.sort_order()
        assert Quality.K1080.sort_order() < Quality.K720.sort_order()
        assert Quality.K720.sort_order() < Quality.K480.sort_order()
        assert Quality.K480.sort_order() < Quality.UNKNOWN.sort_order()


class TestPlaySource:
    """測試播放來源"""

    def test_to_play_string(self):
        """轉換為 TVBox 播放格式"""
        src = PlaySource(
            url="https://example.com/play",
            source_name="飯太硬",
            quality=Quality.K4,
            episode_name="第1集",
        )
        assert src.to_play_string() == "第1集$https://example.com/play"


class TestVideoItem:
    """測試影片項目"""

    def test_best_quality(self):
        """最佳畫質"""
        item = VideoItem(
            vod_id="test_001",
            vod_name="測試電影",
            sources=[
                PlaySource(url="url1", source_name="A", quality=Quality.K720),
                PlaySource(url="url2", source_name="B", quality=Quality.K4),
                PlaySource(url="url3", source_name="C", quality=Quality.K1080),
            ],
        )
        assert item.best_quality() == Quality.K4

    def test_best_quality_empty(self):
        """無來源時"""
        item = VideoItem(vod_id="test", vod_name="test")
        assert item.best_quality() == Quality.UNKNOWN

    def test_to_tvbox_dict(self):
        """轉換為 TVBox JSON dict"""
        item = VideoItem(
            vod_id="test_001",
            vod_name="測試電影",
            vod_pic="https://img.example.com/pic.jpg",
            vod_year="2025",
            sources=[
                PlaySource(
                    url="https://example.com/play/1",
                    source_name="飯太硬",
                    quality=Quality.K4,
                    score=95.0,
                    is_available=True,
                    episode_name="第1集",
                ),
                PlaySource(
                    url="https://example.com/play/2",
                    source_name="肥貓",
                    quality=Quality.K1080,
                    score=80.0,
                    is_available=True,
                    episode_name="第1集",
                ),
            ],
        )

        result = item.to_tvbox_dict()

        assert result["vod_id"] == "test_001"
        assert result["vod_name"] == "測試電影"
        assert result["vod_quality"] == "4K"
        assert "飯太硬·4K" in result["vod_play_from"]
        assert "肥貓·1080P" in result["vod_play_from"]
        assert "$$$" in result["vod_play_from"]  # 線路分隔符
        assert "https://example.com/play/1" in result["vod_play_url"]
        assert "https://example.com/play/2" in result["vod_play_url"]


class TestHealthCheckResult:
    """測試健康檢查結果"""

    def test_create(self):
        """建立健康檢查結果"""
        result = HealthCheckResult(
            url="https://example.com/play",
            source_name="測試源",
            is_available=True,
            http_status=200,
            response_time=1.5,
        )
        assert result.is_available
        assert result.http_status == 200
        assert result.response_time == 1.5
