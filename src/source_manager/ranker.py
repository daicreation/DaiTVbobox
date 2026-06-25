"""
Source Manager — 評分排名
依據健康檢查結果計算 source_score，讀取歷史趨勢
"""
import json
from pathlib import Path
from datetime import datetime, timezone

from .models import HealthScore, SourceScore
from ..utils import logger, load_json, save_json
from ..constants import CACHE_DIR


def calculate_score(health_scores: list[HealthScore]) -> list[SourceScore]:
    """從健康分數計算來源排名"""
    return rank_sources(health_scores)


def rank_sources(health_scores: list[HealthScore]) -> list[SourceScore]:
    """
    讀取歷史分數，合併新數據，輸出排名

    Args:
        health_scores: 新的健康檢查結果列表

    Returns:
        按 score 降序排列的 SourceScore 列表
    """
    # 讀取之前的排名快取
    cache_path = CACHE_DIR / "source_scores.json"
    old_scores: dict[str, SourceScore] = {}
    cached = load_json(cache_path)
    if cached:
        for item in cached.get("sources", []):
            key = item.get("source_key", "")
            old_scores[key] = SourceScore(
                source_key=key,
                source_name=item.get("source_name", ""),
                score=item.get("score", 0),
                history_7d=item.get("history_7d", []),
                trend=item.get("trend", "stable"),
            )

    # 合併新的健康檢查結果
    results: dict[str, SourceScore] = {}
    for hs in health_scores:
        key = hs.source_key
        if key in old_scores:
            ss = old_scores[key]
        else:
            ss = SourceScore(source_key=key, source_name=hs.source_name)
        ss.update(hs.health_score)
        results[key] = ss

    # 排序
    ranked = sorted(results.values(), key=lambda x: x.score, reverse=True)

    # 寫入快取
    save_json({
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {
                "source_key": s.source_key,
                "source_name": s.source_name,
                "score": s.score,
                "trend": s.trend,
                "history_7d": s.history_7d,
            }
            for s in ranked
        ],
    }, cache_path)

    # 輸出排名摘要
    for i, s in enumerate(ranked):
        emoji = "📈" if s.trend == "up" else "📉" if s.trend == "down" else "➡️"
        logger.info(f"  #{i+1} {s.source_name}: {s.score} {emoji}")

    return ranked
