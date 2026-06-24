# ============================================================
# TVBox 影視聚合系統 — 模組②: 健康檢查 (health_checker)
#
# 功能：
#   1. 讀取 source_fetcher 的抓取結果
#   2. 對每個播放 URL 進行 HTTP HEAD 測試 (輕量級)
#   3. 記錄響應時間、HTTP 狀態碼、可用性
#   4. 多次測試以計算穩定性 (stability)
#   5. 將結果寫入快取 (cache/)
#
# 測試策略：
#   - 使用 HEAD 請求 (不下載內容，節省頻寬)
#   - 每個 URL 測試 3 次 (計算平均值與方差)
#   - 分批處理，每批 20 個 (避免同時過多連線)
#   - 只測試新的或上次失敗的 URL (增量檢查)
# ============================================================

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .constants import (
    CACHE_DIR,
    RULES_YAML_PATH,
    MAX_CONCURRENT_FETCHES,
)
from .models import (
    VideoItem,
    PlaySource,
    HealthCheckResult,
    SourceCache,
)
from .utils import (
    logger,
    load_yaml,
    load_json,
    save_json,
    http_head_check,
    now_iso,
    now_display,
    chunk_list,
)


def check_all_sources(
    source_caches: dict[str, SourceCache],
    rules_config: Optional[dict] = None,
) -> dict[str, list[VideoItem]]:
    """
    對所有來源的所有影片進行健康檢查

    這是模組的主入口函數

    Args:
        source_caches: source_fetcher 的輸出
            {"fantaiying": SourceCache(...), ...}
        rules_config: 評分規則配置 (dict)，可選

    Returns:
        {
            "movie": [VideoItem, ...],
            "tv": [VideoItem, ...],
            "variety": [VideoItem, ...],
            "live": [VideoItem, ...],
        }
        每個 VideoItem 的 sources 已更新健康檢查結果
    """
    if rules_config is None:
        rules_config = load_yaml(RULES_YAML_PATH)

    thresholds = rules_config.get("thresholds", {})

    # 收集所有播放 URL
    all_urls: list[dict] = []  # [{"url": ..., "source_name": ..., "item_id": ..., "category": ...}]
    all_items: dict[str, list[VideoItem]] = {"movie": [], "tv": [], "variety": [], "live": []}

    for source_key, cache in source_caches.items():
        for raw_item in cache.items:
            # 重建 VideoItem
            item = _dict_to_item(raw_item)
            category = item.category.value  # "movie" / "tv" / ...

            if category not in all_items:
                category = "movie"

            all_items[category].append(item)

            # 收集 URL 用於健康檢查
            for src in item.sources:
                if src.url:
                    all_urls.append({
                        "url": src.url,
                        "source_name": src.source_name,
                        "item_id": item.vod_id,
                        "category": category,
                        "quality": src.quality.value,
                    })

    # 去重 URL (同一個 URL 可能被多個影片引用)
    unique_urls = list({u["url"]: u for u in all_urls}.values())
    logger.info(f"共 {len(all_urls)} 個播放 URL (去重後 {len(unique_urls)} 個)")

    # 分批進行健康檢查
    batches = chunk_list(unique_urls, 20)
    logger.info(f"分為 {len(batches)} 批，每批最多 20 個 URL")

    all_results: dict[str, HealthCheckResult] = {}  # key = URL

    for batch_idx, batch in enumerate(batches, 1):
        logger.info(f"健康檢查: 第 {batch_idx}/{len(batches)} 批 ({len(batch)} 個 URL)")

        batch_results = _check_batch(batch, thresholds)
        all_results.update(batch_results)

        # 批次間休息 1 秒 (避免被目標伺服器限流)
        if batch_idx < len(batches):
            time.sleep(1)

    # 將健康檢查結果合併回 VideoItem
    _merge_results(all_items, all_results)

    # 保存健康檢查快取
    cache_path = CACHE_DIR / f"health_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_json(
        {
            "checked_at": now_iso(),
            "total_urls": len(unique_urls),
            "available": sum(1 for r in all_results.values() if r.is_available),
            "unavailable": sum(1 for r in all_results.values() if not r.is_available),
            "results": {
                url: {
                    "is_available": r.is_available,
                    "http_status": r.http_status,
                    "response_time": r.response_time,
                    "source_name": r.source_name,
                    "error_message": r.error_message,
                }
                for url, r in all_results.items()
            },
        },
        cache_path,
    )

    # 統計
    for cat, items in all_items.items():
        available_count = sum(
            1 for item in items
            for s in item.sources
            if s.is_available
        )
        logger.info(f"  [{cat}] {len(items)} 個影片, {available_count} 個可用 URL")

    return all_items


def _check_batch(
    batch: list[dict],
    thresholds: dict,
) -> dict[str, HealthCheckResult]:
    """
    檢查一批 URL (並行)

    Args:
        batch: URL 資訊列表
        thresholds: 閾值設定

    Returns:
        {url: HealthCheckResult}
    """
    results: dict[str, HealthCheckResult] = {}
    max_workers = min(MAX_CONCURRENT_FETCHES, len(batch))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_check_single_url, info, thresholds): info["url"]
            for info in batch
        }

        for future in as_completed(future_map):
            url = future_map[future]
            try:
                result = future.result()
                if result:
                    results[url] = result
            except Exception as e:
                logger.debug(f"健康檢查異常 ({url[:60]}): {e}")

    return results


def _check_single_url(
    info: dict,
    thresholds: dict,
    attempts: int = 3,
) -> Optional[HealthCheckResult]:
    """
    對單個 URL 進行多次健康檢查

    執行 3 次 HEAD 請求：
    - 至少 2 次成功 → is_available = True
    - 計算平均響應時間
    - 計算標準差 (stability)

    Args:
        info: URL 資訊 {"url": ..., "source_name": ..., ...}
        thresholds: 閾值設定
        attempts: 測試次數

    Returns:
        HealthCheckResult
    """
    url = info["url"]
    source_name = info.get("source_name", "unknown")

    success_count = 0
    response_times: list[float] = []
    last_status = 0
    last_error = ""

    for attempt in range(1, attempts + 1):
        check = http_head_check(url, timeout=10)

        if check["status"] and 200 <= check["status"] < 500 and check["status"] != 403:
            success_count += 1
            response_times.append(check["response_time"])
            last_status = check["status"]
        else:
            last_error = check.get("error") or f"HTTP {check['status']}"

        # 請求間隔 0.5 秒
        if attempt < attempts:
            time.sleep(0.5)

    # 判斷可用性：至少 2/3 成功
    is_available = success_count >= max(2, attempts // 2 + 1)

    # 計算平均響應時間
    avg_response_time = (
        sum(response_times) / len(response_times)
        if response_times
        else 10.0  # 預設 10 秒 (超時視為慢)
    )

    # 檢查是否符合閾值
    max_response_time = thresholds.get("max_response_time", 10.0)
    min_success_rate = thresholds.get("min_success_rate", 0.7)

    if avg_response_time > max_response_time:
        is_available = False
        if not last_error:
            last_error = f"響應太慢 ({avg_response_time:.2f}s > {max_response_time}s)"

    current_success_rate = success_count / attempts
    if current_success_rate < min_success_rate:
        is_available = False
        if not last_error:
            last_error = f"成功率過低 ({current_success_rate:.0%} < {min_success_rate:.0%})"

    return HealthCheckResult(
        url=url,
        source_name=source_name,
        is_available=is_available,
        http_status=last_status,
        response_time=round(avg_response_time, 3),
        content_length=check.get("content_length", 0),
        content_type=check.get("content_type", ""),
        error_message=last_error,
        checked_at=now_iso(),
        attempt=attempts,
    )


def _merge_results(
    all_items: dict[str, list[VideoItem]],
    health_results: dict[str, HealthCheckResult],
) -> None:
    """
    將健康檢查結果合併回 VideoItem.sources

    對每個 VideoItem 的每個 PlaySource：
    - 更新 is_available
    - 更新 response_time
    - 更新 http_status

    Args:
        all_items: 所有分類的 VideoItem 列表 (會被修改)
        health_results: 健康檢查結果
    """
    for category, items in all_items.items():
        for item in items:
            for src in item.sources:
                if src.url in health_results:
                    result = health_results[src.url]
                    src.is_available = result.is_available
                    src.response_time = result.response_time
                    src.http_status = result.http_status
                    src.last_checked = result.checked_at
                    src.stability = _calculate_stability(
                        result.response_time, result.is_available
                    )


def _calculate_stability(response_time: float, is_available: bool) -> float:
    """
    計算穩定性分數

    穩定性基於響應時間的倒數與可用性：
    - 可用 + 快速響應 = 高分
    - 可用 + 慢速響應 = 中分
    - 不可用 = 0 分

    Args:
        response_time: 平均響應時間 (秒)
        is_available: 是否可用

    Returns:
        穩定性分數 (0.0 ~ 100.0)
    """
    if not is_available:
        return 0.0

    # 響應時間越短，穩定性越高
    # <1.0s → 100 分, <3.0s → 70 分, <5.0s → 40 分, >5.0s → 10 分
    if response_time < 1.0:
        return 100.0
    elif response_time < 3.0:
        return 70.0 + (3.0 - response_time) / 2.0 * 30.0
    elif response_time < 5.0:
        return 40.0 + (5.0 - response_time) / 2.0 * 30.0
    else:
        return max(0.0, 10.0 - (response_time - 5.0) * 5.0)


def _dict_to_item(raw: dict) -> VideoItem:
    """
    從快取 dict 重建 VideoItem

    用於從 source_fetcher 的快取中恢復數據

    Args:
        raw: VideoItem 的 dict 表示

    Returns:
        VideoItem 實例
    """
    sources = []
    for src_dict in raw.get("sources", []):
        sources.append(PlaySource(
            url=src_dict.get("url", ""),
            source_name=src_dict.get("source_name", ""),
            quality=Quality.from_string(src_dict.get("quality", "")),
            episode_name=src_dict.get("episode_name", "第1集"),
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


# 需要從 models import (放在檔案末尾避免循環引用)
from .models import Quality


# ---- 命令列入口 ----
if __name__ == "__main__":
    from .utils import setup_logging
    setup_logging("INFO")
    print("=" * 60)
    print("TVBox 健康檢查模組 — 本機測試")
    print("=" * 60)
    # 本機測試需要先有 source_fetcher 的快取
    # 這裡提供一個簡單的測試範例
    from .constants import CACHE_DIR
    import glob
    cache_files = list(CACHE_DIR.glob("health_check_*.json"))
    print(f"已找到 {len(cache_files)} 個健康檢查快取")
