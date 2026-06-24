# ============================================================
# TVBox 影視聚合系統 — JSON 生成器測試
# ============================================================

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.builder import (
    build_all_outputs,
    _dedup_and_merge,
    _limit_sources,
    _tag_platform,
    _build_tvbox_json,
)
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
