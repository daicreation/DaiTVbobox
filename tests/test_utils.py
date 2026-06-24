# ============================================================
# TVBox 影視聚合系統 — 共用工具測試
# ============================================================

import sys
from pathlib import Path

# 確保 src/ 在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import (
    normalize_title,
    levenshtein_ratio,
    detect_platform,
    parse_episode_info,
    chunk_list,
    safe_get,
)


class TestNormalizeTitle:
    """測試標題正規化"""

    def test_normalize_basic(self):
        """基本正規化"""
        assert normalize_title("範例電影") == "範例電影"

    def test_normalize_with_year(self):
        """去除年份"""
        assert normalize_title("範例電影 (2025)") == "範例電影"

    def test_normalize_with_quality(self):
        """去除畫質標記"""
        result = normalize_title("範例電影 4K HD")
        assert "4k" not in result
        assert "hd" not in result
        assert "範例電影" in result

    def test_normalize_chinese_brackets(self):
        """去除中文括號"""
        result = normalize_title("範例電影（特別篇）")
        assert "範例電影" in result
        assert "特別篇" not in result

    def test_normalize_empty(self):
        """空字串處理"""
        assert normalize_title("") == ""
        assert normalize_title(None) == ""


class TestLevenshteinRatio:
    """測試字串相似度"""

    def test_identical(self):
        """相同字串"""
        assert levenshtein_ratio("abc", "abc") == 1.0

    def test_completely_different(self):
        """完全不同"""
        assert levenshtein_ratio("abc", "xyz") < 0.5

    def test_similar(self):
        """相似字串"""
        ratio = levenshtein_ratio("範例電影", "範例電影2025")
        assert ratio >= 0.6  # 應該有一定相似度（至少60%）

    def test_empty(self):
        """空字串"""
        assert levenshtein_ratio("", "abc") == 0.0
        assert levenshtein_ratio("abc", "") == 0.0


class TestDetectPlatform:
    """測試平台檢測"""

    def test_iqiyi(self):
        """檢測愛奇藝"""
        platform_map = {
            "iqiyi": {"name": "愛奇藝", "keywords": ["iqiyi", "愛奇藝"]},
            "tencent": {"name": "騰訊", "keywords": ["tencent", "騰訊"]},
        }
        assert detect_platform("某劇·愛奇藝", platform_map) == "愛奇藝"
        assert detect_platform("iqiyi_source", platform_map) == "愛奇藝"

    def test_no_match(self):
        """無匹配"""
        platform_map = {"iqiyi": {"name": "愛奇藝", "keywords": ["iqiyi"]}}
        assert detect_platform("某劇·優酷", platform_map) == ""

    def test_empty_text(self):
        """空文字"""
        platform_map = {"iqiyi": {"name": "愛奇藝", "keywords": ["iqiyi"]}}
        assert detect_platform("", platform_map) == ""


class TestParseEpisodeInfo:
    """測試集數解析"""

    def test_update_to(self):
        """更新至 N 集"""
        total, updated = parse_episode_info("更新至24集")
        assert updated == 24

    def test_full_episodes(self):
        """全 N 集"""
        total, updated = parse_episode_info("40集全")
        assert total == 40
        assert updated == 40

    def test_no_info(self):
        """無集數資訊"""
        total, updated = parse_episode_info("這是一個電影")
        assert total == 0
        assert updated == 0


class TestChunkList:
    """測試列表切割"""

    def test_basic(self):
        """基本切割"""
        result = chunk_list([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_exact(self):
        """剛好整除"""
        result = chunk_list([1, 2, 3, 4], 2)
        assert result == [[1, 2], [3, 4]]

    def test_empty(self):
        """空列表"""
        result = chunk_list([], 5)
        assert result == []


class TestSafeGet:
    """測試安全取值"""

    def test_basic(self):
        """基本巢狀取值"""
        data = {"a": {"b": {"c": 42}}}
        assert safe_get(data, "a", "b", "c") == 42

    def test_missing_key(self):
        """鍵不存在"""
        data = {"a": {"b": 42}}
        assert safe_get(data, "a", "c", default=None) is None
        assert safe_get(data, "x", default="N/A") == "N/A"
