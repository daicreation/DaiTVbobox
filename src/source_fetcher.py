# ============================================================
# TVBox 影視聚合系統 — 模組①: 來源抓取 (source_fetcher)
#
# 功能：
#   1. 讀取 config/sources.yaml 取得上游源列表
#   2. 並行從多個上游源抓取最新 JSON 數據
#   3. 解析為 VideoItem + PlaySource 內部數據模型
#   4. 將原始數據暫存到 sources/ 目錄
#   5. 支援自動重試、超時處理
#
# 使用方式：
#   python -m src.source_fetcher
#   或作為模組被 GitHub Actions 調用
# ============================================================

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .constants import (
    SOURCES_YAML_PATH,
    SOURCES_DIR,
    HTTP_HEADERS,
    DEFAULT_TIMEOUT,
    MAX_CONCURRENT_FETCHES,
)
from .models import (
    VideoItem,
    PlaySource,
    Quality,
    Category,
    SourceCache,
)
from .utils import (
    logger,
    load_yaml,
    save_json,
    create_http_client,
    http_get,
    now_iso,
    safe_get,
    parse_episode_info,
    detect_platform,
)


def fetch_all_sources(rules_config: Optional[dict] = None) -> dict[str, SourceCache]:
    """
    從所有啟用的上游源抓取數據

    這是模組的主入口函數

    Args:
        rules_config: 評分規則配置 (dict)，可選

    Returns:
        {
            "fantaiying": SourceCache(...),
            "feimao": SourceCache(...),
            ...
        }
    """
    # 1. 讀取來源配置
    raw_config = load_yaml(SOURCES_YAML_PATH)
    sources = raw_config.get("sources", {})
    settings = raw_config.get("settings", {})

    if not sources:
        logger.error("沒有找到任何上游源配置！請檢查 config/sources.yaml")
        return {}

    # 只抓取啟用的來源
    enabled_sources = {
        key: cfg
        for key, cfg in sources.items()
        if cfg.get("enabled", True)
    }

    logger.info(f"共 {len(sources)} 個來源，{len(enabled_sources)} 個已啟用")

    # 2. 並行抓取 (使用 ThreadPoolExecutor)
    results: dict[str, SourceCache] = {}
    max_workers = min(MAX_CONCURRENT_FETCHES, len(enabled_sources))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 建立一個共用的 HTTP 客戶端 (在每個 thread 中獨立建立)
        future_map = {
            executor.submit(_fetch_single_source, key, cfg, settings): key
            for key, cfg in enabled_sources.items()
        }

        for future in as_completed(future_map):
            source_key = future_map[future]
            try:
                cache = future.result()
                if cache:
                    results[source_key] = cache
                    logger.info(
                        f"✓ [{cache.source_name}] 抓取完成: "
                        f"{cache.item_count} 個影片, "
                        f"{cache.raw_size:,} bytes"
                    )
                else:
                    logger.warning(f"✗ [{source_key}] 抓取失敗 (返回 None)")
            except Exception as e:
                logger.error(f"✗ [{source_key}] 抓取異常: {type(e).__name__}: {e}")

    logger.info(f"抓取完成: {len(results)}/{len(enabled_sources)} 個來源成功")
    return results


def _fetch_single_source(
    source_key: str,
    source_cfg: dict,
    settings: dict,
) -> Optional[SourceCache]:
    """
    抓取單個上游源

    Args:
        source_key: 來源識別碼 (如 "fantaiying")
        source_cfg: 來源配置 dict
        settings: 全局設定

    Returns:
        SourceCache 物件，失敗返回 None
    """
    source_name = source_cfg.get("name", source_key)
    url = source_cfg.get("url", "")
    timeout = source_cfg.get("timeout", settings.get("default_timeout", DEFAULT_TIMEOUT))
    encoding = source_cfg.get("encoding", "utf-8")

    if not url:
        logger.error(f"[{source_name}] 沒有配置 URL，跳過")
        return None

    logger.info(f"[{source_name}] 開始抓取: {url}")

    # 1. 發送 HTTP 請求
    client = create_http_client(timeout)
    try:
        raw_text = http_get(url, client=client, timeout=timeout, encoding=encoding)
    except Exception as e:
        logger.error(f"[{source_name}] 抓取失敗 (已重試): {e}")
        return None
    finally:
        client.close()

    if not raw_text:
        return None

    raw_size = len(raw_text.encode(encoding))

    # 2. 解析 JSON
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error(f"[{source_name}] JSON 解析失敗: {e}")
        # 嘗試修復常見問題：BOM、多餘逗號
        try:
            cleaned = raw_text.lstrip("﻿").strip()
            data = json.loads(cleaned)
            logger.info(f"[{source_name}] JSON 修復後解析成功")
        except json.JSONDecodeError:
            return None

    # 3. 保存原始數據 (供除錯用)
    sources_dir = SOURCES_DIR / source_key
    sources_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = sources_dir / f"raw_{today}.json"
    save_json(data, raw_path, compress=True)

    # 4. 解析為內部數據模型
    items = _parse_source_data(data, source_name, source_cfg)

    # 5. 建立快取物件
    cache = SourceCache(
        source_key=source_key,
        source_name=source_name,
        fetched_at=now_iso(),
        item_count=len(items),
        raw_size=raw_size,
        items=[_item_to_dict(it) for it in items],
    )

    return cache


def _parse_source_data(
    data: dict,
    source_name: str,
    source_cfg: dict,
) -> list[VideoItem]:
    """
    解析上游源的 JSON 數據為 VideoItem 列表

    支援多種 JSON 格式：
    - TVBox 標準格式: {"list": [...]}
    - 部分源可能用 "data" / "videos" / "items" 等鍵名
    - 部分源直接返回列表

    Args:
        data: 從上游抓取的原始 JSON
        source_name: 來源名稱
        source_cfg: 來源配置

    Returns:
        VideoItem 列表
    """
    items = []

    # 嘗試多種可能的鍵名
    raw_list = (
        safe_get(data, "list")
        or safe_get(data, "data")
        or safe_get(data, "videos")
        or safe_get(data, "items")
        or safe_get(data, "result")
    )

    # 如果上述鍵名都沒找到，嘗試 data 本身是否為列表
    if raw_list is None and isinstance(data, list):
        raw_list = data

    if not isinstance(raw_list, list):
        logger.warning(f"[{source_name}] 無法從 JSON 中找到影片列表，keys: {list(data.keys())[:5]}")
        return items

    # 解析每個影片項目
    for raw_item in raw_list:
        if not isinstance(raw_item, dict):
            continue

        try:
            item = _parse_single_video(raw_item, source_name)
            if item:
                items.append(item)
        except Exception as e:
            logger.debug(f"[{source_name}] 解析單個影片失敗: {e}")
            continue

    logger.debug(f"[{source_name}] 解析出 {len(items)} 個影片")
    return items


def _parse_single_video(raw: dict, source_name: str) -> Optional[VideoItem]:
    """
    解析單個影片的 JSON 為 VideoItem

    處理欄位名稱不一致的問題（不同源可能有不同命名）

    Args:
        raw: 單個影片的原始 dict
        source_name: 來源名稱

    Returns:
        VideoItem 實例，解析失敗返回 None
    """
    # 提取核心欄位（支援多種命名方式）
    vod_id = (
        safe_get(raw, "vod_id", default="")
        or safe_get(raw, "id", default="")
        or safe_get(raw, "video_id", default="")
        or f"auto_{hash(safe_get(raw, 'vod_name', default='unknown'))}"
    )
    vod_name = (
        safe_get(raw, "vod_name", default="")
        or safe_get(raw, "name", default="")
        or safe_get(raw, "title", default="")
    )

    if not vod_name:
        return None  # 沒有名稱的項目跳過

    # 解析畫質（從備註、標題、來源標記中提取）
    remarks = safe_get(raw, "vod_remarks", default="")
    quality = _extract_quality(remarks + " " + vod_name)

    # 解析播放 URL
    play_url = safe_get(raw, "vod_play_url", default="")
    if not play_url:
        # 嘗試其他可能的鍵名
        play_url = (
            safe_get(raw, "play_url", default="")
            or safe_get(raw, "url", default="")
            or safe_get(raw, "source_url", default="")
        )

    # 建立 PlaySource
    source = PlaySource(
        url=play_url if play_url else "",
        source_name=source_name,
        quality=quality,
        episode_name="第1集",
    )

    # 建立 VideoItem
    item = VideoItem(
        vod_id=str(vod_id),
        vod_name=vod_name,
        vod_pic=safe_get(raw, "vod_pic", default="")
        or safe_get(raw, "pic", default="")
        or safe_get(raw, "poster", default=""),
        vod_remarks=remarks or f"{quality.value}·{source_name}",
        type_name=safe_get(raw, "type_name", default="")
        or safe_get(raw, "type", default=""),
        vod_year=safe_get(raw, "vod_year", default="")
        or safe_get(raw, "year", default=""),
        vod_area=safe_get(raw, "vod_area", default="")
        or safe_get(raw, "area", default=""),
        vod_actor=safe_get(raw, "vod_actor", default="")
        or safe_get(raw, "actor", default=""),
        vod_director=safe_get(raw, "vod_director", default="")
        or safe_get(raw, "director", default=""),
        vod_content=safe_get(raw, "vod_content", default="")
        or safe_get(raw, "content", default="")
        or safe_get(raw, "description", default=""),
        vod_score=safe_get(raw, "vod_score", default="")
        or safe_get(raw, "score", default="")
        or safe_get(raw, "rating", default=""),
        sources=[source],
    )

    return item


def _extract_quality(text: str) -> Quality:
    """
    從文字中提取畫質資訊

    按優先級檢查：4K > 1080P > 720P > 480P

    Args:
        text: 包含畫質資訊的文字

    Returns:
        Quality 枚舉值
    """
    text_upper = text.upper()

    if any(kw in text_upper for kw in ("4K", "2160P", "UHD", "超清", "極清", "原畫")):
        return Quality.K4
    if any(kw in text_upper for kw in ("1080P", "1080", "FHD", "BLURAY", "藍光", "高清")):
        return Quality.K1080
    if any(kw in text_upper for kw in ("720P", "720", "HD", "標清", "高清")):
        # 注意：「高清」可能對應 1080P 也對應 720P，以 1080P 優先
        return Quality.K720
    if any(kw in text_upper for kw in ("480P", "480", "SD", "流暢")):
        return Quality.K480

    return Quality.UNKNOWN


def _item_to_dict(item: VideoItem) -> dict:
    """
    將 VideoItem 轉換為 dict（用於快取）

    Args:
        item: VideoItem 實例

    Returns:
        dict 格式的影片數據
    """
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


# ---- 命令列入口 (方便本機測試) ----
if __name__ == "__main__":
    from .utils import setup_logging
    setup_logging("INFO")
    print("=" * 60)
    print("TVBox 來源抓取模組 — 本機測試")
    print("=" * 60)
    results = fetch_all_sources()
    for key, cache in results.items():
        print(f"  [{cache.source_name}] {cache.item_count} 個影片")
    print(f"\n總計 {len(results)} 個來源成功")
