# ============================================================
# TVBox 影視聚合系統 — 模組④: JSON 生成 (builder)
#
# 功能：
#   1. 讀取 ranker 排序後的數據
#   2. 使用 Levenshtein 去重合併同一影片的不同來源
#   3. 生成 TVBox 兼容的 JSON 格式
#   4. 分別輸出 movie.json / tv.json / variety.json / live.json
#   5. 自動標記 4K、平台等資訊
#   6. 控制輸出大小 (max_items, max_sources_per_video)
#
# TVBox JSON 格式:
#   {
#     "class": [...],     ← 分類列表
#     "filters": {...},   ← 篩選器
#     "list": [...],      ← 影片列表
#     "total": N,
#     "page": 1,
#     "pagecount": N,
#     "limit": 50,
#     "update_time": "..."
#   }
# ============================================================

from datetime import datetime
from pathlib import Path
from typing import Optional

from .constants import (
    OUTPUT_DIR,
    RULES_YAML_PATH,
    TVBOX_CLASSES,
    QUALITY_ORDER,
)
from .models import (
    VideoItem,
    PlaySource,
    Quality,
    Category,
)
from .utils import (
    logger,
    load_yaml,
    save_json,
    normalize_title,
    levenshtein_ratio,
    detect_platform,
    now_display,
)


def build_all_outputs(
    all_items: dict[str, list[VideoItem]],
    rules_config: Optional[dict] = None,
    domain: str = "https://tv.xxx.com",
) -> dict[str, Path]:
    """
    生成所有 TVBox JSON 輸出

    這是模組的主入口函數

    步驟：
    1. 去重合併 (按類別分別處理)
    2. 標記 4K / 平台
    3. 限制來源數量
    4. 生成 TVBox 兼容 JSON
    5. 寫入 output/*.json
    6. 生成主 config.json

    Args:
        all_items: ranker 的輸出
        rules_config: 評分規則
        domain: Worker 域名 (用於 config.json 中的 api URL)

    Returns:
        {類別: 輸出檔案路徑}
    """
    if rules_config is None:
        rules_config = load_yaml(RULES_YAML_PATH)

    dedup_config = rules_config.get("dedup", {})
    output_config = rules_config.get("output", {})
    platform_map = rules_config.get("platform_keywords", {})

    similarity_threshold = dedup_config.get("title_similarity_threshold", 0.80)
    max_items = output_config.get("max_items_per_category", 5000)
    max_sources = output_config.get("max_sources_per_video", 10)
    compress = output_config.get("compress_json", False)
    time_fmt = output_config.get("update_time_format", "%Y-%m-%d %H:%M:%S")
    update_time = now_display(time_fmt)

    output_paths: dict[str, Path] = {}

    # 每個類別分別處理
    for category_key in ["movie", "tv", "variety", "live"]:
        items = all_items.get(category_key, [])
        if not items:
            logger.warning(f"[{category_key}] 沒有數據，生成空 JSON")
            items = []

        logger.info(f"生成 [{category_key}] JSON: {len(items)} 個影片 (合併前)")

        # 步驟 1: 去重合併
        merged_items = _dedup_and_merge(
            items,
            similarity_threshold,
            max_sources,
        )
        logger.info(f"  [{category_key}] 合併後: {len(merged_items)} 個影片")

        # 步驟 2: 標記平台 (僅電視劇)
        if category_key == "tv":
            for item in merged_items:
                _tag_platform(item, platform_map)

        # 步驟 3: 限制數量
        if len(merged_items) > max_items:
            logger.warning(
                f"  [{category_key}] 影片數量 {len(merged_items)} > 上限 {max_items}，截斷"
            )
            merged_items = merged_items[:max_items]

        # 步驟 4: 生成 TVBox JSON
        tvbox_data = _build_tvbox_json(
            merged_items,
            category_key,
            update_time,
            max_sources,
        )

        # 步驟 5: 寫入 output/
        output_file = OUTPUT_DIR / f"{category_key}.json"
        save_json(tvbox_data, output_file, compress)
        output_paths[category_key] = output_file

        logger.info(
            f"  [{category_key}] 輸出: {output_file.name} "
            f"({len(tvbox_data.get('list', []))} 個影片)"
        )

    # 步驟 6: 生成主 config.json
    config_path = _build_config_json(domain, output_paths, compress)
    output_paths["config"] = config_path

    logger.info(f"所有輸出已生成: {len(output_paths)} 個檔案")
    return output_paths


def _dedup_and_merge(
    items: list[VideoItem],
    similarity_threshold: float,
    max_sources_per_video: int,
) -> list[VideoItem]:
    """
    使用 Levenshtein 距離對影片列表進行去重合併

    處理邏輯：
    1. 正規化所有標題
    2. 對每個影片，尋找相似度 > threshold 的其他影片
    3. 合併它們的 sources
    4. 保留畫質較好的那一個的 metadata (海報、簡介等)
    5. 每個影片最多保留 max_sources_per_video 個來源

    Args:
        items: 待合併的影片列表 (可能來自多個源)
        similarity_threshold: 相似度閾值
        max_sources_per_video: 每個影片最大來源數

    Returns:
        去重合併後的影片列表
    """
    if not items:
        return []

    # 正規化所有標題
    normalized_titles = [normalize_title(item.vod_name) for item in items]

    # 使用 Union-Find 風格進行聚類
    n = len(items)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    # 比較每對影片 (O(n²)，以 5000 個影片來說約 1250 萬次比較)
    # 優化：只比較標題長度相近的 (長度差 < 10)
    for i in range(n):
        title_i = normalized_titles[i]
        len_i = len(title_i)
        for j in range(i + 1, n):
            title_j = normalized_titles[j]
            len_j = len(title_j)

            # 長度差太多，直接跳過
            if abs(len_i - len_j) > 10:
                continue

            # 計算相似度
            similarity = levenshtein_ratio(title_i, title_j)
            if similarity >= similarity_threshold:
                union(i, j)

    # 按群組聚合
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        if root not in groups:
            groups[root] = []
        groups[root].append(i)

    # 合併每個群組
    merged: list[VideoItem] = []
    for root, indices in groups.items():
        if len(indices) == 1:
            # 只有一個，直接保留 (但限制來源數)
            item = items[indices[0]]
            item.sources = _limit_sources(item.sources, max_sources_per_video)
            merged.append(item)
        else:
            # 多個影片合併
            group_items = [items[i] for i in indices]

            # 選擇畫質最好的 item 作為基底
            best_item = max(group_items, key=lambda x: x.best_quality().sort_order())

            # 合併所有來源
            all_sources: list[PlaySource] = []
            seen_urls: set[str] = set()
            for gi in group_items:
                for src in gi.sources:
                    # 去除重複 URL
                    if src.url not in seen_urls:
                        seen_urls.add(src.url)
                        all_sources.append(src)

            # 按分數排序
            all_sources.sort(key=lambda s: s.score, reverse=True)

            # 限制來源數
            all_sources = _limit_sources(all_sources, max_sources_per_video)

            # 更新備註 (標記來源數)
            best_item.sources = all_sources
            source_names = list(dict.fromkeys(s.source_name for s in all_sources[:5]))
            quality = best_item.best_quality()
            best_item.vod_remarks = (
                f"{quality.value}·{'·'.join(source_names)}·{len(all_sources)}源"
            )

            merged.append(best_item)

    # 按最佳畫質排序
    merged.sort(key=lambda x: x.best_quality().sort_order())

    return merged


def _limit_sources(sources: list[PlaySource], max_count: int) -> list[PlaySource]:
    """
    限制每個影片的來源數量

    優先保留：
    1. 高畫質 (4K > 1080P > 720P)
    2. 高分數
    3. 不同來源 (至少每個來源保留一個)

    Args:
        sources: 來源列表
        max_count: 最大保留數

    Returns:
        限制後的來源列表
    """
    if len(sources) <= max_count:
        return sources

    # 按畫質+分數排序
    sorted_src = sorted(
        sources,
        key=lambda s: (s.quality.sort_order(), -s.score),
    )

    result: list[PlaySource] = []
    seen_names: set[str] = set()

    # 第一輪：每個來源至少保留一個 (最高分的那個)
    for src in sorted_src:
        if src.source_name not in seen_names:
            result.append(src)
            seen_names.add(src.source_name)
        if len(result) >= max_count:
            break

    # 第二輪：如果還有空間，補充高分來源
    if len(result) < max_count:
        for src in sorted_src:
            if src not in result:
                result.append(src)
            if len(result) >= max_count:
                break

    return result[:max_count]


def _tag_platform(item: VideoItem, platform_map: dict) -> None:
    """
    為電視劇標記平台 (愛奇藝/騰訊/優酷/芒果)

    從以下欄位檢測：
    - vod_remarks (備註)
    - vod_play_from (播放線路名)
    - vod_name (劇名)

    Args:
        item: 影片項目 (會被修改)
        platform_map: 平台關鍵字映射
    """
    # 組合所有文字
    text_parts = [
        item.vod_name,
        item.vod_remarks,
        item.type_name,
    ]
    # 也檢查來源名稱
    for src in item.sources:
        text_parts.append(src.source_name)

    combined = " ".join(text_parts)

    platform = detect_platform(combined, platform_map)
    if platform:
        item.platform = platform


def _build_tvbox_json(
    items: list[VideoItem],
    category_key: str,
    update_time: str,
    max_sources: int,
) -> dict:
    """
    生成 TVBox 兼容的 JSON 結構

    Args:
        items: 影片列表 (已合併、排序)
        category_key: 類別鍵名 (movie / tv / variety / live)
        update_time: 更新時間字串
        max_sources: 每個影片最大來源數

    Returns:
        TVBox JSON dict
    """
    # 取得分類定義
    classes = TVBOX_CLASSES.get(category_key, [])

    # 生成影片列表
    video_list: list[dict] = []
    for item in items:
        # 限制每個 item 的來源數
        item.sources = _limit_sources(item.sources, max_sources)

        # 轉換為 TVBox 格式
        tvbox_item = item.to_tvbox_dict()

        # 補充 TVBox 專屬欄位
        tvbox_item["vod_remarks"] = item.vod_remarks
        tvbox_item["type_name"] = item.type_name or "未知"
        tvbox_item["vod_year"] = item.vod_year
        tvbox_item["vod_area"] = item.vod_area
        tvbox_item["vod_actor"] = item.vod_actor
        tvbox_item["vod_director"] = item.vod_director
        tvbox_item["vod_content"] = item.vod_content
        tvbox_item["vod_score"] = item.vod_score

        video_list.append(tvbox_item)

    total = len(video_list)

    return {
        "class": classes,
        "filters": _build_filters(category_key),
        "list": video_list,
        "total": total,
        "page": 1,
        "pagecount": max(1, total // 50 + (1 if total % 50 else 0)),
        "limit": 50,
        "update_time": update_time,
    }


def _build_filters(category_key: str) -> dict:
    """
    建立篩選器

    為不同類別提供適當的篩選選項

    Args:
        category_key: 類別鍵名

    Returns:
        篩選器 dict
    """
    filters = {
        "0": [
            {
                "key": "year",
                "name": "年份",
                "value": [
                    {"n": "全部", "v": "0"},
                    {"n": "2025", "v": "2025"},
                    {"n": "2024", "v": "2024"},
                    {"n": "2023", "v": "2023"},
                    {"n": "2022", "v": "2022"},
                    {"n": "更早", "v": "old"},
                ],
            },
        ]
    }

    # 非直播類別加入畫質篩選
    if category_key != "live":
        filters["0"].append({
            "key": "quality",
            "name": "畫質",
            "value": [
                {"n": "全部", "v": "0"},
                {"n": "4K", "v": "4k"},
                {"n": "1080P", "v": "1080p"},
                {"n": "720P", "v": "720p"},
            ],
        })

    # 電影類別加入地區篩選
    if category_key == "movie":
        filters["0"].append({
            "key": "area",
            "name": "地區",
            "value": [
                {"n": "全部", "v": "0"},
                {"n": "中國", "v": "中國"},
                {"n": "美國", "v": "美國"},
                {"n": "韓國", "v": "韓國"},
                {"n": "日本", "v": "日本"},
                {"n": "其他", "v": "其他"},
            ],
        })

    # 電視劇類別加入平台篩選
    if category_key == "tv":
        filters["0"].append({
            "key": "platform",
            "name": "平台",
            "value": [
                {"n": "全部", "v": "0"},
                {"n": "愛奇藝", "v": "iqiyi"},
                {"n": "騰訊", "v": "tencent"},
                {"n": "優酷", "v": "youku"},
                {"n": "芒果", "v": "mgtv"},
            ],
        })

    return filters


def _build_config_json(
    domain: str,
    output_paths: dict[str, Path],
    compress: bool,
) -> Path:
    """
    生成主 config.json (TVBox 入口)

    包含 storeHouse (多倉入口) 和主 sites 配置

    Args:
        domain: Worker 域名
        output_paths: 各類別的輸出檔案路徑
        compress: 是否壓縮 JSON

    Returns:
        config.json 的路徑
    """
    config = {
        "storeHouse": [
            {
                "sourceName": "🎬 電影",
                "sourceUrl": f"{domain}/movie",
            },
            {
                "sourceName": "📺 電視劇",
                "sourceUrl": f"{domain}/tv",
            },
            {
                "sourceName": "🎪 綜藝",
                "sourceUrl": f"{domain}/variety",
            },
            {
                "sourceName": "📡 直播",
                "sourceUrl": f"{domain}/live",
            },
        ],
        "sites": [
            {
                "key": "聚合搜尋",
                "name": "🎯 聚合搜尋|4K 1080P 720P",
                "type": 3,
                "api": f"{domain}/api",
                "searchable": 1,
                "quickSearch": 1,
                "filterable": 1,
                "jar": f"{domain}/spider.jar",
            }
        ],
        "lives": [
            {
                "group": "央視",
                "name": "CCTV-1 綜合",
                "urls": [f"{domain}/live"],
            }
        ],
        "flags": [
            "4K", "1080P", "720P",
            "優酷", "愛奇藝", "騰訊", "芒果",
        ],
        "wallpaper": f"{domain}/wallpaper.jpg",
        "logo": f"{domain}/logo.png",
        "spider": f"{domain}/spider.jar",
        "update_time": now_display(),
    }

    config_path = OUTPUT_DIR / "config.json"
    save_json(config, config_path, compress)

    return config_path


# ---- 命令列入口 ----
if __name__ == "__main__":
    from .utils import setup_logging
    setup_logging("INFO")
    print("=" * 60)
    print("TVBox JSON 生成模組 — 測試")
    print("=" * 60)

    # 建立測試數據
    test_src_4k = PlaySource(
        url="https://example.com/play/movie1/4k",
        source_name="飯太硬",
        quality=Quality.K4,
        score=90.0,
        is_available=True,
    )
    test_src_1080 = PlaySource(
        url="https://example.com/play/movie1/1080",
        source_name="肥貓",
        quality=Quality.K1080,
        score=75.0,
        is_available=True,
    )

    test_item1 = VideoItem(
        vod_id="movie_001",
        vod_name="測試電影 (2025)",
        vod_pic="https://img.example.com/poster1.jpg",
        vod_remarks="4K·飯太硬·肥貓",
        type_name="動作",
        vod_year="2025",
        vod_area="美國",
        vod_actor="演員A / 演員B",
        vod_director="導演X",
        vod_content="這是一部測試電影的簡介。",
        vod_score="8.5",
        sources=[test_src_4k, test_src_1080],
    )

    test_data = {"movie": [test_item1], "tv": [], "variety": [], "live": []}
    rules = load_yaml(RULES_YAML_PATH)
    paths = build_all_outputs(test_data, rules, "https://tv.xxx.com")

    print("\n輸出檔案:")
    for cat, path in paths.items():
        print(f"  {cat}: {path}")
