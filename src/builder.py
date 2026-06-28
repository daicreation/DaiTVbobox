"""Chill-AI-TV — Builder: build TVBox config and content outputs."""

from __future__ import annotations

from copy import deepcopy
from typing import Iterable
from urllib.parse import parse_qs, quote, urlparse

from .constants import (
    CATEGORIES,
    OUTPUT_DIR,
    OUTPUT_CONFIG_CN_JSON,
    OUTPUT_CONFIG_HK_JSON,
    OUTPUT_HOT_TV_JSON,
    TVBOX_CLASSES,
    WORKER_DOMAIN,
)
from .hot_tv import (
    build_direct_hot_tv_dataset,
    build_hot_tv_dataset,
    fetch_hot_tv_feed,
    fetch_hot_variety_feed,
)
from .models import Category, VideoItem
from .utils import detect_platform, levenshtein_ratio, normalize_title, now_display, save_json


SITE_NAME_BLOCKLIST = (
    "采集",
    "理論",
    "理论",
    "福利",
    "成人",
    "色",
    "直播",
    "短剧",
    "短劇",
    "云盘",
    "雲盤",
    "网盘",
    "網盤",
    "alist",
    "配置",
)
SITE_URL_BLOCKLIST = (
    ".js",
    ".py",
    "drpy",
    "spider",
    "get.js",
    "/lib/",
    "live?url=",
    "csp_",
    "/vod/json",
    "json?url=",
)
SITE_URL_ALLOWLIST = (
    "api.php/provide/vod",
    "/provide/vod/",
    "/provide/vod?",
)
TV_KEYWORDS = (
    "劇",
    "剧",
    "連續劇",
    "连续剧",
    "電視劇",
    "电视剧",
    "國產劇",
    "国产剧",
    "港台劇",
    "港台剧",
    "日韓劇",
    "日韩剧",
    "歐美劇",
    "欧美剧",
)
VARIETY_KEYWORDS = (
    "綜藝",
    "综艺",
    "真人秀",
    "脱口秀",
    "脫口秀",
    "晚會",
    "晚会",
    "音樂會",
    "音乐会",
)
LIVE_KEYWORDS = ("直播", "卫视", "衛視", "央視", "央视", "体育", "體育")
CORE_SITE_ORDER = ["chill", "bfzy", "ff", "sn", "lz", "360", "js", "jy", "yh", "md", "ik", "wj", "ry"]


DEFAULT_FILTERS = {
    "movie": {
        "0": [
            {
                "key": "year",
                "name": "年份",
                "value": [
                    {"n": "全部", "v": "0"},
                    {"n": "2026", "v": "2026"},
                    {"n": "2025", "v": "2025"},
                    {"n": "2024", "v": "2024"},
                    {"n": "2023", "v": "2023"},
                    {"n": "更早", "v": "old"},
                ],
            },
            {
                "key": "quality",
                "name": "畫質",
                "value": [
                    {"n": "全部", "v": "0"},
                    {"n": "4K", "v": "4k"},
                    {"n": "1080P", "v": "1080p"},
                    {"n": "720P", "v": "720p"},
                ],
            },
        ]
    },
    "tv": {
        "0": [
            {
                "key": "year",
                "name": "年份",
                "value": [
                    {"n": "全部", "v": "0"},
                    {"n": "2026", "v": "2026"},
                    {"n": "2025", "v": "2025"},
                    {"n": "2024", "v": "2024"},
                    {"n": "2023", "v": "2023"},
                    {"n": "更早", "v": "old"},
                ],
            },
            {
                "key": "platform",
                "name": "平台",
                "value": [
                    {"n": "全部", "v": "0"},
                    {"n": "愛奇藝", "v": "iqiyi"},
                    {"n": "騰訊", "v": "tencent"},
                    {"n": "優酷", "v": "youku"},
                    {"n": "芒果", "v": "mgtv"},
                ],
            },
        ]
    },
    "variety": {"0": []},
    "live": {},
}


def _core_sites(domain: str) -> list[dict]:
    base = (domain or WORKER_DOMAIN).rstrip("/")
    core_sites = [
        {
            "key": "chill",
            "name": "🧊 Chill-TV",
            "type": 1,
            "api": f"{base}/api",
            "searchable": 1,
            "quickSearch": 1,
            "filterable": 1,
        },
        {"key": "bfzy", "name": "🔥 暴風", "type": 1, "api": f"{base}/p/bfzy", "searchable": 1, "quickSearch": 1},
        {"key": "ff", "name": "⚡ 非凡", "type": 1, "api": f"{base}/p/ff", "searchable": 1, "quickSearch": 1},
        {"key": "sn", "name": "🎯 索尼", "type": 1, "api": f"{base}/p/sn", "searchable": 1, "quickSearch": 1},
        {"key": "lz", "name": "🔮 量子", "type": 1, "api": f"{base}/p/lz", "searchable": 1, "quickSearch": 1},
        {"key": "360", "name": "💠 360", "type": 1, "api": f"{base}/p/360", "searchable": 1, "quickSearch": 1},
        {"key": "js", "name": "⚡ 極速", "type": 1, "api": f"{base}/p/js", "searchable": 1, "quickSearch": 1},
        {"key": "jy", "name": "🦅 金鷹", "type": 1, "api": f"{base}/p/jy", "searchable": 1, "quickSearch": 1},
        {"key": "yh", "name": "🌸 櫻花", "type": 1, "api": f"{base}/p/yh", "searchable": 1, "quickSearch": 1},
        {"key": "md", "name": "🏙️ 魔都", "type": 1, "api": f"{base}/p/md", "searchable": 1, "quickSearch": 1},
        {"key": "ik", "name": "🎵 iKun", "type": 1, "api": f"{base}/p/ik", "searchable": 1, "quickSearch": 1},
        {"key": "wj", "name": "♾️ 無盡", "type": 1, "api": f"{base}/p/wj", "searchable": 1, "quickSearch": 1},
        {"key": "ry", "name": "🍀 如意", "type": 1, "api": f"{base}/p/ry", "searchable": 1, "quickSearch": 1},
    ]
    order = {key: index for index, key in enumerate(CORE_SITE_ORDER)}
    return sorted(core_sites, key=lambda site: order.get(site["key"], 999))


def _limit_sources(sources, max_sources_per_video: int):
    unique = {}
    for src in sorted(sources, key=lambda s: (s.score, -s.response_time), reverse=True):
        key = (src.source_name, src.url)
        if key not in unique:
            unique[key] = src
    return list(unique.values())[:max_sources_per_video]


def _tag_platform(item: VideoItem, platform_map: dict) -> VideoItem:
    if item.platform:
        return item
    text = " ".join([item.vod_name, item.vod_remarks, item.type_name, " ".join(s.source_name for s in item.sources)])
    item.platform = detect_platform(text, platform_map)
    return item


def _looks_like_tv(item: VideoItem, text: str) -> bool:
    if item.episode_count > 0 or item.episode_updated > 0:
        return True
    if "更新至" in text or "全" in text and "集" in text:
        return True
    return any(keyword in text for keyword in TV_KEYWORDS)


def _classify_item(item: VideoItem) -> str:
    text = " ".join(
        part for part in [item.vod_name, item.vod_remarks, item.type_name, item.vod_content] if part
    )
    if item.type_name == "站點":
        return "config"
    if item.vod_name.startswith("[直播]") or any(keyword in text for keyword in LIVE_KEYWORDS):
        return "live"
    if any(keyword in text for keyword in VARIETY_KEYWORDS):
        return "variety"
    if _looks_like_tv(item, text):
        return "tv"
    return "movie"


def _merge_item_fields(target: VideoItem, source: VideoItem) -> None:
    for field_name in (
        "vod_pic",
        "vod_remarks",
        "type_name",
        "vod_year",
        "vod_area",
        "vod_actor",
        "vod_director",
        "vod_content",
        "vod_score",
        "platform",
    ):
        if not getattr(target, field_name) and getattr(source, field_name):
            setattr(target, field_name, getattr(source, field_name))
    target.episode_count = max(target.episode_count, source.episode_count)
    target.episode_updated = max(target.episode_updated, source.episode_updated)


def _dedup_and_merge(items: list[VideoItem], similarity_threshold: float, max_sources_per_video: int) -> list[VideoItem]:
    merged: list[VideoItem] = []
    for item in items:
        if not item.vod_name:
            continue
        candidate = deepcopy(item)
        candidate.sources = list(item.sources)
        candidate_key = normalize_title(candidate.vod_name)
        match = None
        for existing in merged:
            existing_key = normalize_title(existing.vod_name)
            if candidate_key == existing_key or levenshtein_ratio(candidate_key, existing_key) >= similarity_threshold:
                match = existing
                break
        if match is None:
            candidate.sources = _limit_sources(candidate.sources, max_sources_per_video)
            merged.append(candidate)
            continue

        match.sources.extend(candidate.sources)
        match.sources = _limit_sources(match.sources, max_sources_per_video)
        _merge_item_fields(match, candidate)

    return merged


def _sort_items(items: list[VideoItem]) -> list[VideoItem]:
    def sort_key(item: VideoItem):
        best_score = max((src.score for src in item.sources), default=0)
        source_count = len([src for src in item.sources if src.is_available])
        try:
            year = int(str(item.vod_year).strip() or 0)
        except ValueError:
            year = 0
        return (item.best_quality().sort_order(), -best_score, -year, -source_count, item.vod_name)

    return sorted(items, key=sort_key)


def _rewrite_hot_tv_images(dataset: dict, domain: str) -> dict:
    base = (domain or WORKER_DOMAIN).rstrip("/")

    def unwrap_proxy_url(url: str) -> str:
        parsed = urlparse(url)
        if parsed.path != "/img":
            return url
        inner = parse_qs(parsed.query).get("url", [""])[0].strip()
        return inner or url

    def proxify(url: str) -> str:
        value = str(url or "").strip()
        if not value.startswith(("http://", "https://")):
            return value
        value = unwrap_proxy_url(value)
        return f"{base}/img?url={quote(value, safe='')}"

    for item in dataset.get("list", []) or []:
        if "vod_pic" in item:
            item["vod_pic"] = proxify(item.get("vod_pic", ""))

    for detail in (dataset.get("details", {}) or {}).values():
        if "vod_pic" in detail:
            detail["vod_pic"] = proxify(detail.get("vod_pic", ""))

    return dataset


def _merge_homepage_datasets(*datasets: dict) -> dict:
    merged_list = []
    merged_details = {}

    for dataset in datasets:
        for item in dataset.get("list", []) or []:
            vod_id = item.get("vod_id")
            if not vod_id or vod_id in merged_details:
                continue
            merged_list.append(item)
        for vod_id, detail in (dataset.get("details", {}) or {}).items():
            if vod_id not in merged_details:
                merged_details[vod_id] = detail

    return {
        "update_time": now_display(),
        "list": merged_list,
        "details": merged_details,
    }


def _build_tvbox_json(items: list[VideoItem], category: str, update_time: str, max_sources_per_video: int) -> dict:
    prepared = []
    for item in items:
        candidate = deepcopy(item)
        candidate.sources = _limit_sources(candidate.sources, max_sources_per_video)
        prepared.append(candidate.to_tvbox_dict())

    return {
        "class": TVBOX_CLASSES[category],
        "filters": DEFAULT_FILTERS.get(category, {}),
        "list": prepared,
        "total": len(prepared),
        "page": 1,
        "pagecount": max(1, (len(prepared) + 49) // 50),
        "limit": 50,
        "update_time": update_time,
    }


def _site_allowed(name: str, url: str) -> bool:
    name_lower = name.lower()
    url_lower = url.lower()
    if any(keyword.lower() in name_lower for keyword in SITE_NAME_BLOCKLIST):
        return False
    if any(keyword in url_lower for keyword in SITE_URL_BLOCKLIST):
        return False
    if not any(keyword in url_lower for keyword in SITE_URL_ALLOWLIST):
        return False
    if not url_lower.startswith("http"):
        return False
    return True


def _discover_sites(all_items: dict[str, list[VideoItem]]) -> list[dict]:
    sites = []
    seen = set()
    for items in all_items.values():
        for item in items:
            if item.type_name != "站點" or not item.sources:
                continue
            src = item.sources[0]
            name = item.vod_name.replace("[站點] ", "").replace("[直播] ", "").strip()
            if not src.is_available or not _site_allowed(name, src.url) or src.url in seen:
                continue
            seen.add(src.url)
            sites.append(
                {
                    "key": "auto_" + (name[:12] or "site"),
                    "name": name,
                    "type": 1,
                    "api": src.url,
                    "searchable": 1,
                    "quickSearch": 1,
                }
            )
    return sites


def _build_config(all_items: dict[str, list[VideoItem]], domain: str, update_time: str, region: str) -> dict:
    core_sites = _core_sites(domain)
    discovered = _discover_sites(all_items)
    seen_apis = {site["api"] for site in core_sites}
    sites = list(core_sites)
    for site in discovered:
        if site["api"] not in seen_apis:
            seen_apis.add(site["api"])
            sites.append(site)
    return {
        "sites": sites,
        "update_time": update_time,
        "region": region,
    }


def _iter_items(all_items: dict[str, list[VideoItem]]) -> Iterable[VideoItem]:
    for items in all_items.values():
        for item in items:
            yield item


def build_all_outputs(all_items=None, rules_config=None, domain=""):
    rules_config = rules_config or {}
    output_cfg = rules_config.get("output", {})
    dedup_cfg = rules_config.get("dedup", {})
    max_items = output_cfg.get("max_items_per_category", 5000)
    max_sources_per_video = output_cfg.get("max_sources_per_video", 10)
    similarity_threshold = dedup_cfg.get("title_similarity_threshold", 0.80)
    update_time = now_display(output_cfg.get("update_time_format", "%Y-%m-%d %H:%M:%S"))
    platform_map = rules_config.get("platform_keywords", {})

    typed_items = {key: [] for key in CATEGORIES}
    if all_items:
        for item in _iter_items(all_items):
            item = deepcopy(item)
            _tag_platform(item, platform_map)
            category = _classify_item(item)
            if category in typed_items:
                item.category = Category.from_string(category)
                typed_items[category].append(item)

    paths = {}
    ranked_items_by_category: dict[str, list[VideoItem]] = {}
    for category, meta in CATEGORIES.items():
        items = _dedup_and_merge(typed_items[category], similarity_threshold, max_sources_per_video)
        items = _sort_items(items)[:max_items]
        ranked_items_by_category[category] = items
        data = _build_tvbox_json(items, category, update_time, max_sources_per_video)
        output_path = meta["output_file"]
        save_json(data, output_path)
        paths[category] = output_path

    hot_tv_feed_items = fetch_hot_tv_feed()
    hot_variety_feed_items = fetch_hot_variety_feed()

    hot_tv_dataset = {"list": [], "details": {}, "update_time": update_time}
    if hot_tv_feed_items:
        hot_tv_dataset = build_hot_tv_dataset(
            hot_tv_feed_items,
            ranked_items_by_category.get("tv", []),
            similarity_threshold,
        )
        if not hot_tv_dataset.get("list"):
            hot_tv_dataset = build_direct_hot_tv_dataset(
                hot_tv_feed_items,
                similarity_threshold,
            )

    hot_variety_dataset = {"list": [], "details": {}, "update_time": update_time}
    if hot_variety_feed_items:
        hot_variety_dataset = build_hot_tv_dataset(
            hot_variety_feed_items,
            ranked_items_by_category.get("variety", []),
            similarity_threshold,
        )
        if not hot_variety_dataset.get("list"):
            hot_variety_dataset = build_direct_hot_tv_dataset(
                hot_variety_feed_items,
                similarity_threshold,
            )

    hot_tv_dataset = _merge_homepage_datasets(hot_tv_dataset, hot_variety_dataset)
    hot_tv_dataset = _rewrite_hot_tv_images(hot_tv_dataset, domain)
    save_json(hot_tv_dataset, OUTPUT_HOT_TV_JSON)
    paths["hot_tv"] = OUTPUT_HOT_TV_JSON

    config_path = OUTPUT_DIR / "config.json"
    shared_config = _build_config(all_items or typed_items, domain, update_time, "shared")
    save_json(shared_config, config_path)
    save_json(shared_config, OUTPUT_CONFIG_HK_JSON)
    save_json(shared_config, OUTPUT_CONFIG_CN_JSON)
    paths["config"] = config_path
    paths["config_hk"] = OUTPUT_CONFIG_HK_JSON
    paths["config_cn"] = OUTPUT_CONFIG_CN_JSON

    return paths
