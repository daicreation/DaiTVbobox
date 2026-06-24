# ============================================================
# TVBox 影視聚合系統 — 模組③: 評分排序 (ranker)
#
# 功能：
#   1. 讀取 health_checker 的結果 (含每個 URL 的可用性/速度/穩定性)
#   2. 根據評分公式計算每個 PlaySource 的綜合分數
#   3. 按分數對每個 VideoItem 的 sources 進行排序
#   4. 過濾不合格的來源 (低於 min_score)
#
# 評分公式:
#   score = speed_score × 0.25
#         + success_rate_score × 0.30
#         + stability_score × 0.25
#         + quality_score × 0.20
#
# 每個維度都是 0~100 分，加權後總分也是 0~100 分
# ============================================================

from pathlib import Path
from typing import Optional

from .models import (
    VideoItem,
    PlaySource,
    Quality,
)
from .constants import RULES_YAML_PATH
from .utils import (
    logger,
    load_yaml,
    now_display,
)


def rank_all_items(
    all_items: dict[str, list[VideoItem]],
    rules_config: Optional[dict] = None,
) -> dict[str, list[VideoItem]]:
    """
    對所有分類的所有影片進行評分排序

    這是模組的主入口函數

    處理流程:
    1. 讀取評分規則
    2. 對每個 VideoItem 的每個 PlaySource 計算分數
    3. 過濾低分來源
    4. 按分數降序排列每個影片的來源列表
    5. 按規則對影片列表排序 (4K 優先 > 高分 > 新內容)

    Args:
        all_items: health_checker 的輸出
            {"movie": [VideoItem, ...], ...}
        rules_config: 評分規則配置 (dict)，可選

    Returns:
        排序後的 all_items (原地修改 + 返回)
    """
    if rules_config is None:
        rules_config = load_yaml(RULES_YAML_PATH)

    scoring_rules = rules_config.get("scoring", {})
    thresholds = rules_config.get("thresholds", {})
    ranking_order = rules_config.get("ranking", {}).get("order", [])

    # 取得評分權重
    weights = scoring_rules.get("weights", {
        "speed": 0.25,
        "success_rate": 0.30,
        "stability": 0.25,
        "quality": 0.20,
    })

    # 取得畫質加分
    quality_bonus = scoring_rules.get("quality_bonus", {
        "4K": 100, "1080P": 70, "720P": 40, "480P": 10, "未知": 0,
    })

    # 取得閾值
    min_score = thresholds.get("min_score", 50)

    total_scored = 0
    total_filtered = 0

    for category, items in all_items.items():
        logger.info(f"評分 [{category}]: {len(items)} 個影片")

        for item in items:
            # 對每個來源計算分數
            for src in item.sources:
                src.score = _calculate_source_score(
                    src, weights, quality_bonus
                )
                total_scored += 1

            # 過濾低分來源
            original_count = len(item.sources)
            item.sources = [
                s for s in item.sources
                if s.score >= min_score and s.is_available
            ]
            total_filtered += (original_count - len(item.sources))

            # 按分數降序排列來源
            item.sources.sort(key=lambda s: s.score, reverse=True)

        # 對影片列表進行排序
        items.sort(key=lambda item: _item_sort_key(item, ranking_order), reverse=True)

        logger.info(
            f"  [{category}] 完成: {len(items)} 個影片, "
            f"過濾 {total_filtered} 個低分來源"
        )

    logger.info(
        f"評分完成: 共評分 {total_scored} 個來源, "
        f"過濾 {total_filtered} 個不合格來源"
    )

    return all_items


def _calculate_source_score(
    src: PlaySource,
    weights: dict,
    quality_bonus: dict,
) -> float:
    """
    計算單個 PlaySource 的綜合評分

    公式:
      score = speed_score × w_speed
            + success_rate_score × w_success
            + stability_score × w_stability
            + quality_score × w_quality

    Args:
        src: 播放來源 (已包含健康檢查結果)
        weights: 各維度權重
        quality_bonus: 畫質加分對照表

    Returns:
        綜合評分 (0.0 ~ 100.0)
    """
    # ---- 1. 速度分數 (0~100) ----
    # 響應時間越短，分數越高
    # <0.5s → 100, <2s → 80, <5s → 50, >10s → 0
    response_time = src.response_time
    if response_time <= 0:
        speed_score = 0.0
    elif response_time < 0.5:
        speed_score = 100.0
    elif response_time < 2.0:
        speed_score = 80.0 + (2.0 - response_time) / 1.5 * 20.0
    elif response_time < 5.0:
        speed_score = 50.0 + (5.0 - response_time) / 3.0 * 30.0
    elif response_time < 10.0:
        speed_score = max(0.0, (10.0 - response_time) / 5.0 * 50.0)
    else:
        speed_score = 0.0

    # ---- 2. 成功率分數 (0~100) ----
    # 可用 = 100, 不可用 = 0
    success_rate_score = 100.0 if src.is_available else 0.0

    # ---- 3. 穩定性分數 (0~100) ----
    # 直接使用 health_checker 計算的穩定性分數
    stability_score = src.stability

    # ---- 4. 畫質分數 (0~100) ----
    # 從 quality_bonus 查表
    quality_score = quality_bonus.get(src.quality.value, 0)

    # ---- 計算加權總分 ----
    score = (
        speed_score * weights.get("speed", 0.25)
        + success_rate_score * weights.get("success_rate", 0.30)
        + stability_score * weights.get("stability", 0.25)
        + quality_score * weights.get("quality", 0.20)
    )

    # 儲存各維度分數供除錯
    src.speed_score = round(speed_score, 1)
    src.quality_score = round(quality_score, 1)
    src.success_rate = 1.0 if src.is_available else 0.0

    return round(score, 1)


def _item_sort_key(item: VideoItem, ranking_order: list[str]) -> tuple:
    """
    生成 VideoItem 的排序鍵

    排序優先級 (從 ranking_order 讀取):
    1. quality — 畫質 (4K > 1080P > 720P, 數字越小越好)
    2. score — 平均來源分數 (越高越好)
    3. year — 年份 (越新越好)
    4. source_count — 可用來源數 (越多越好)

    Args:
        item: 影片項目
        ranking_order: 排序優先級列表

    Returns:
        排序用的 tuple (所有值越大越好，所以對 quality 取負數)
    """
    # 計算平均來源分數
    avg_score = (
        sum(s.score for s in item.sources) / max(len(item.sources), 1)
        if item.sources
        else 0.0
    )

    # 畫質排序：4K=4, 1080P=3, 720P=2, 480P=1, 未知=0
    quality_rank = {
        Quality.K4: 4,
        Quality.K1080: 3,
        Quality.K720: 2,
        Quality.K480: 1,
        Quality.UNKNOWN: 0,
    }.get(item.best_quality(), 0)

    # 年份：嘗試轉為整數
    try:
        year = int(item.vod_year)
    except (ValueError, TypeError):
        year = 0

    # 來源數
    source_count = len([s for s in item.sources if s.is_available])

    # 按 ranking_order 建立排序 tuple
    sort_values = []
    for key in ranking_order:
        if key == "quality":
            sort_values.append(quality_rank)
        elif key == "score":
            sort_values.append(round(avg_score, 1))
        elif key == "year":
            sort_values.append(year)
        elif key == "source_count":
            sort_values.append(source_count)

    return tuple(sort_values)


# ---- 命令列入口 ----
if __name__ == "__main__":
    from .utils import setup_logging
    setup_logging("INFO")
    print("=" * 60)
    print("TVBox 評分排序模組 — 測試")
    print("=" * 60)

    # 建立測試數據
    test_src_4k = PlaySource(
        url="https://example.com/play/4k",
        source_name="飯太硬",
        quality=Quality.K4,
        response_time=1.5,
        is_available=True,
        stability=85.0,
    )
    test_src_1080 = PlaySource(
        url="https://example.com/play/1080",
        source_name="肥貓",
        quality=Quality.K1080,
        response_time=3.0,
        is_available=True,
        stability=70.0,
    )
    test_item = VideoItem(
        vod_id="test_001",
        vod_name="測試電影",
        vod_year="2025",
        sources=[test_src_4k, test_src_1080],
    )

    test_data = {"movie": [test_item]}
    rules = load_yaml(RULES_YAML_PATH)
    ranked = rank_all_items(test_data, rules)

    for item in ranked.get("movie", []):
        print(f"\n影片: {item.vod_name}")
        for src in item.sources:
            print(f"  {src.source_name} | {src.quality.value} | "
                  f"速度:{src.speed_score} | 穩定:{src.stability} | "
                  f"畫質:{src.quality_score} | 總分:{src.score}")
