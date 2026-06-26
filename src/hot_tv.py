"""Build pre-matched Douban recommendation datasets for the Chill-TV homepage."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable

import httpx

from .models import Category, VideoItem
from .utils import create_http_client, levenshtein_ratio, logger, normalize_title, now_display

DOUBAN_HOT_TV_API = (
    "https://m.douban.com/rexxar/api/v2/subject_collection/tv_domestic/items"
    "?start=0&count=15"
)
DOUBAN_HOT_TV_REFERER = "https://m.douban.com/subject_collection/tv_domestic"
DOUBAN_HOT_VARIETY_API = (
    "https://m.douban.com/rexxar/api/v2/subject_collection/show_hot/items"
    "?start=0&count=15"
)
DOUBAN_HOT_VARIETY_REFERER = "https://m.douban.com/subject_collection/show_hot"
DIRECT_HOT_TV_SOURCES = (
    ("bfzy", "https://bfzyapi.com/api.php/provide/vod/"),
    ("ff", "http://cj.ffzyapi.com/api.php/provide/vod"),
    ("sn", "https://suoniapi.com/api.php/provide/vod"),
    ("lz", "https://cj.lziapi.com/api.php/provide/vod/"),
    ("360", "https://360zyzz.com/api.php/provide/vod/"),
    ("js", "https://jszyapi.com/api.php/provide/vod/"),
    ("jy", "https://jyzyapi.com/provide/vod/"),
    ("yh", "https://m3u8.apiyhzy.com/api.php/provide/vod"),
    ("wj", "https://api.wujinapi.me/api.php/provide/vod/"),
    ("md", "https://www.mdzyapi.com/api.php/provide/vod/"),
    ("ik", "https://ikunzyapi.com/api.php/provide/vod/"),
    ("tgzy", "http://360.tgzy.cc/api.php/provide/vod/"),
    ("tvcaiji", "http://tvcaiji.pankk.cn/api.php/provide/vod/"),
    ("xydm", "http://xydm.baicai.buzz/api.php/provide/vod/"),
    ("nxflv", "http://caiji.nxflv.com/api.php/provide/vod/"),
    ("hykjtv", "http://tv2.hykjtv.cn/api.php/provide/vod/"),
    ("vipmv", "http://vipmv.cc/api.php/provide/vod/"),
    ("v47", "http://47.113.126.237:1234/api.php/provide/vod/"),
)


def fetch_hot_tv_feed() -> list[dict]:
    """Fetch hot TV feed items from Douban's stable mobile JSON endpoint."""
    return _fetch_subject_collection_feed(DOUBAN_HOT_TV_API, DOUBAN_HOT_TV_REFERER)


def fetch_hot_variety_feed() -> list[dict]:
    """Fetch hot variety-show feed items from Douban's stable mobile JSON endpoint."""
    return _fetch_subject_collection_feed(DOUBAN_HOT_VARIETY_API, DOUBAN_HOT_VARIETY_REFERER)


def _fetch_subject_collection_feed(api_url: str, referer: str) -> list[dict]:
    """Fetch a Douban subject_collection feed using the mobile JSON endpoint."""
    client = create_http_client(timeout=20)
    try:
        response = client.get(
            api_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": referer,
            },
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning(f"_fetch_subject_collection_feed failed: {type(exc).__name__}: {exc}")
        return []
    finally:
        client.close()

    if not isinstance(payload, dict):
        return []

    raw_items = payload.get("subject_collection_items")
    if not isinstance(raw_items, list):
        return []

    feed_items: list[dict] = []
    for raw_item in raw_items:
        feed_item = _parse_hot_tv_feed_item(raw_item)
        if feed_item:
            feed_items.append(feed_item)
    return feed_items


def match_hot_tv_items(
    feed_items: list[dict],
    ranked_tv_items: list[VideoItem],
    similarity_threshold: float,
) -> list[dict]:
    """Match hot-feed titles to ranked playable items."""
    matched_rows: list[dict] = []
    candidates = [item for item in ranked_tv_items if _playable_source_count(item) > 0]
    used_vod_ids: set[str] = set()

    for feed_item in feed_items:
        descriptor = _build_feed_descriptor(feed_item)
        if not descriptor.normalized_title:
            continue

        best_item = _find_best_match(descriptor, candidates, similarity_threshold, used_vod_ids)
        if not best_item:
            continue

        used_vod_ids.add(best_item.vod_id)
        matched_rows.append(
            {
                "feed": feed_item,
                "item": best_item,
                "similarity": levenshtein_ratio(
                    descriptor.normalized_title,
                    normalize_title(best_item.vod_name),
                ),
            }
        )

    return matched_rows


def build_hot_tv_dataset(
    feed_items: list[dict],
    ranked_tv_items: list[VideoItem],
    similarity_threshold: float,
) -> dict:
    """Build homepage cards plus detail payloads for matched hot TV titles."""
    rows = match_hot_tv_items(feed_items, ranked_tv_items, similarity_threshold)
    matched_titles = {
        _build_feed_descriptor(row["feed"]).normalized_title
        for row in rows
    }
    missing_feed_items = [
        feed_item
        for feed_item in feed_items
        if _build_feed_descriptor(feed_item).normalized_title not in matched_titles
    ]

    if missing_feed_items:
        direct_dataset = build_direct_hot_tv_dataset(
            missing_feed_items,
            similarity_threshold,
        )
        rows.extend(
            {
                "feed": {
                    "title": item["vod_name"],
                    "cover": item.get("vod_pic", ""),
                    "remarks": item.get("vod_remarks", ""),
                    "alt_titles": [],
                },
                "item": None,
                "detail": detail,
            }
            for item, detail in (
                (card, direct_dataset["details"].get(card["vod_id"]))
                for card in direct_dataset.get("list", [])
            )
            if detail
        )
    homepage_list: list[dict] = []
    details: dict[str, dict] = {}

    for row in rows:
        feed = row["feed"]
        item = row.get("item")
        detail = row.get("detail") or (_build_detail_payload(item) if item else None)
        if detail:
            details[detail["vod_id"]] = detail
            vod_id = detail["vod_id"]
            vod_name = detail["vod_name"]
            vod_pic = feed.get("cover") or detail["vod_pic"]
            vod_remarks = feed.get("remarks") or detail["vod_remarks"]
            vod_year = detail["vod_year"]
            vod_area = detail["vod_area"]
            vod_actor = detail["vod_actor"]
            vod_content = detail["vod_content"]
            vod_score = detail["vod_score"]
            source_count = detail["source_count"]
        else:
            descriptor = _build_feed_descriptor(feed)
            vod_id = _build_direct_hot_tv_id(descriptor)
            vod_name = str(feed.get("title", "") or "").strip()
            vod_pic = str(feed.get("cover", "") or "").strip()
            vod_remarks = str(feed.get("remarks", "") or "").strip()
            vod_year = str(feed.get("year", "") or "").strip()
            vod_area = ""
            vod_actor = ""
            vod_content = ""
            vod_score = ""
            source_count = 0

        homepage_list.append(
            {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_actor": vod_actor,
                "vod_content": vod_content,
                "vod_score": vod_score,
                "source_count": source_count,
            }
        )

    return {
        "update_time": now_display(),
        "list": homepage_list,
        "details": details,
    }


def build_direct_hot_tv_dataset(
    feed_items: list[dict],
    similarity_threshold: float,
    direct_sources: tuple[tuple[str, str], ...] | None = None,
) -> dict:
    """Build hot TV data by searching the direct-source APIs title by title."""
    homepage_list: list[dict] = []
    details: dict[str, dict] = {}
    source_targets = direct_sources or DIRECT_HOT_TV_SOURCES

    if not feed_items:
        return {
            "update_time": now_display(),
            "list": homepage_list,
            "details": details,
        }

    client = create_http_client(timeout=15)
    try:
        for feed_item in feed_items:
            detail = _build_direct_hot_tv_detail(
                client,
                feed_item,
                similarity_threshold,
                source_targets,
            )
            if not detail:
                continue

            details[detail["vod_id"]] = detail
            homepage_list.append(
                {
                    "vod_id": detail["vod_id"],
                    "vod_name": detail["vod_name"],
                    "vod_pic": feed_item.get("cover") or detail["vod_pic"],
                    "vod_remarks": feed_item.get("remarks") or detail["vod_remarks"],
                    "vod_year": detail["vod_year"],
                    "vod_area": detail["vod_area"],
                    "vod_actor": detail["vod_actor"],
                    "vod_content": detail["vod_content"],
                    "vod_score": detail["vod_score"],
                    "source_count": detail["source_count"],
                }
            )
    finally:
        client.close()

    return {
        "update_time": now_display(),
        "list": homepage_list,
        "details": details,
    }


@dataclass(frozen=True)
class FeedDescriptor:
    title: str
    normalized_title: str
    year: str = ""
    alt_titles: tuple[str, ...] = ()


def _parse_hot_tv_feed_item(raw_item: object) -> dict | None:
    if not isinstance(raw_item, dict) or raw_item.get("type") != "tv":
        return None

    title = str(raw_item.get("title", "")).strip()
    if not title:
        return None

    pic = raw_item.get("pic")
    cover = _pick_hot_tv_cover(pic if isinstance(pic, dict) else {})
    return {
        "title": title,
        "year": str(raw_item.get("year", "")).strip(),
        "cover": cover,
        "remarks": _build_hot_tv_remarks(raw_item),
        "alt_titles": _extract_hot_tv_alt_titles(raw_item),
    }


def _pick_hot_tv_cover(pic: dict) -> str:
    for key in ("large", "normal", "small"):
        value = str(pic.get(key, "")).strip()
        if value:
            return value
    return ""


def _build_hot_tv_remarks(raw_item: dict) -> str:
    parts: list[str] = []

    episodes_info = str(raw_item.get("episodes_info", "")).strip()
    if episodes_info:
        parts.append(episodes_info)

    rating = raw_item.get("rating")
    if isinstance(rating, dict):
        rating_count = _coerce_positive_number(rating.get("count"))
        rating_value = _coerce_positive_number(rating.get("value"))
        if rating_count is not None and rating_value is not None:
            parts.append(f"{rating_value:g}分")

    return " / ".join(parts[:2])


def _extract_hot_tv_alt_titles(raw_item: dict) -> list[str]:
    alt_titles: list[str] = []
    for key in ("original_title",):
        value = str(raw_item.get(key, "")).strip()
        if value and value not in alt_titles:
            alt_titles.append(value)
    return alt_titles


def _coerce_positive_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _find_best_match(
    descriptor: FeedDescriptor,
    candidates: Iterable[VideoItem],
    similarity_threshold: float,
    used_vod_ids: set[str],
) -> VideoItem | None:
    available_candidates = [item for item in candidates if item.vod_id not in used_vod_ids]
    feed_titles = _feed_match_titles(descriptor)
    exact_matches = [
        item
        for item in available_candidates
        if _has_exact_title_overlap(feed_titles, _item_title_candidates(item).all_titles)
    ]
    if exact_matches:
        return _choose_best_candidate(exact_matches)

    best_item: VideoItem | None = None
    best_key: tuple = ()
    for item in available_candidates:
        titles = _item_title_candidates(item)
        if not titles.primary_title:
            continue

        similarity = max(
            levenshtein_ratio(feed_title, candidate_title)
            for feed_title in feed_titles
            for candidate_title in titles.all_titles
        )
        if similarity < similarity_threshold:
            continue

        key = (
            1 if item.category == Category.TV else 0,
            round(similarity, 6),
            _playable_source_score(item),
        )
        if best_item is None or key > best_key:
            best_item = item
            best_key = key

    return best_item


@dataclass(frozen=True)
class ItemTitleCandidates:
    primary_title: str
    all_titles: tuple[str, ...]


def _build_feed_descriptor(feed_item: dict) -> FeedDescriptor:
    title = str(feed_item.get("title", "")).strip()
    normalized_title = normalize_title(title)
    year = str(feed_item.get("year", "")).strip()
    alt_titles = tuple(
        normalized
        for normalized in (
            normalize_title(str(raw_title).strip())
            for raw_title in feed_item.get("alt_titles", []) or []
        )
        if normalized
    )
    return FeedDescriptor(
        title=title,
        normalized_title=normalized_title,
        year=year,
        alt_titles=alt_titles,
    )


def _item_title_candidates(item: VideoItem) -> ItemTitleCandidates:
    primary_title = normalize_title(item.vod_name)
    alternate_titles = []
    raw_alt_titles = item.sources[0].extra.get("alt_titles", []) if item.sources else []
    for raw_title in raw_alt_titles:
        normalized = normalize_title(str(raw_title).strip())
        if normalized and normalized != primary_title:
            alternate_titles.append(normalized)
    all_titles = (primary_title, *alternate_titles) if primary_title else tuple(alternate_titles)
    return ItemTitleCandidates(primary_title=primary_title, all_titles=all_titles)


def _feed_match_titles(descriptor: FeedDescriptor) -> tuple[str, ...]:
    titles: list[str] = []
    for title in (descriptor.normalized_title, *descriptor.alt_titles):
        if title and title not in titles:
            titles.append(title)
    return tuple(titles)


def _has_exact_title_overlap(feed_titles: tuple[str, ...], item_titles: tuple[str, ...]) -> bool:
    return any(feed_title == item_title for feed_title in feed_titles for item_title in item_titles)


def _choose_best_candidate(candidates: Iterable[VideoItem]) -> VideoItem | None:
    best_item: VideoItem | None = None
    best_key: tuple = ()

    for item in candidates:
        key = (
            1 if item.category == Category.TV else 0,
            _playable_source_score(item),
        )
        if best_item is None or key > best_key:
            best_item = item
            best_key = key

    return best_item


def _playable_source_count(item: VideoItem) -> int:
    return len(_playable_sources(item))


def _playable_source_score(item: VideoItem) -> float:
    return sum(src.score for src in _playable_sources(item))


def _playable_sources(item: VideoItem) -> list:
    return [
        src
        for src in item.sources
        if src.is_available and str(src.url or "").strip()
    ]


def _build_direct_hot_tv_detail(
    client: httpx.Client,
    feed_item: dict,
    similarity_threshold: float,
    direct_sources: tuple[tuple[str, str], ...],
) -> dict | None:
    descriptor = _build_feed_descriptor(feed_item)
    if not descriptor.normalized_title:
        return None

    source_details: list[dict] = []
    for source_name, base_url in direct_sources:
        detail = _search_direct_source_detail(
            client,
            source_name,
            base_url,
            feed_item,
            descriptor,
            similarity_threshold,
        )
        if detail:
            source_details.append(detail)

    return _merge_direct_source_details(feed_item, descriptor, source_details)


def _search_direct_source_detail(
    client: httpx.Client,
    source_name: str,
    base_url: str,
    feed_item: dict,
    descriptor: FeedDescriptor,
    similarity_threshold: float,
) -> dict | None:
    search_match = _search_direct_source_match(
        client,
        base_url,
        feed_item,
        descriptor,
        similarity_threshold,
    )
    if not search_match:
        return None

    vod_id = str(search_match.get("vod_id") or search_match.get("id") or "").strip()
    if not vod_id:
        return None

    payload = _request_direct_source_json(
        client,
        base_url,
        {"ac": "detail", "ids": vod_id},
    )
    detail_items = _extract_direct_source_items(payload)
    if not detail_items:
        return None

    for detail_item in detail_items:
        detail_vod_id = str(detail_item.get("vod_id") or detail_item.get("id") or "").strip()
        if detail_vod_id and detail_vod_id != vod_id:
            continue
        merged_detail = dict(search_match)
        merged_detail.update(detail_item)
        if not str(merged_detail.get("vod_play_url", "")).strip():
            continue
        merged_detail["_source_name"] = source_name
        return merged_detail

    return None


def _search_direct_source_match(
    client: httpx.Client,
    base_url: str,
    feed_item: dict,
    descriptor: FeedDescriptor,
    similarity_threshold: float,
) -> dict | None:
    best_match: dict | None = None
    best_key: tuple = ()

    for query in _feed_search_queries(feed_item):
        payload = _request_direct_source_json(client, base_url, {"wd": query})
        for candidate in _extract_direct_source_items(payload):
            key = _direct_source_match_key(candidate, descriptor, similarity_threshold)
            if not key:
                continue
            if best_match is None or key > best_key:
                best_match = candidate
                best_key = key

    return best_match


def _direct_source_match_key(
    candidate: dict,
    descriptor: FeedDescriptor,
    similarity_threshold: float,
) -> tuple | None:
    candidate_titles = _direct_source_titles(candidate)
    if not candidate_titles:
        return None

    feed_titles = _feed_match_titles(descriptor)
    exact_match = _has_exact_title_overlap(feed_titles, candidate_titles)
    similarity = max(
        levenshtein_ratio(feed_title, candidate_title)
        for feed_title in feed_titles
        for candidate_title in candidate_titles
    )
    if not exact_match and similarity < similarity_threshold:
        return None

    candidate_year = str(candidate.get("vod_year", "")).strip()
    return (
        1 if exact_match else 0,
        1 if descriptor.year and candidate_year == descriptor.year else 0,
        round(similarity, 6),
        1 if str(candidate.get("vod_play_url", "")).strip() else 0,
    )


def _direct_source_titles(candidate: dict) -> tuple[str, ...]:
    titles: list[str] = []
    for raw_title in (candidate.get("vod_name"), candidate.get("vod_en")):
        normalized = normalize_title(str(raw_title or "").strip())
        if normalized and normalized not in titles:
            titles.append(normalized)
    return tuple(titles)


def _feed_search_queries(feed_item: dict) -> tuple[str, ...]:
    queries: list[str] = []
    for raw_query in (feed_item.get("title"), *(feed_item.get("alt_titles") or [])):
        query = str(raw_query or "").strip()
        if query and query not in queries:
            queries.append(query)
    return tuple(queries)


def _request_direct_source_json(
    client: httpx.Client,
    base_url: str,
    params: dict[str, str],
) -> dict | None:
    try:
        response = client.get(base_url, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning(
            "direct hot tv request failed: %s %s params=%s",
            type(exc).__name__,
            base_url,
            params,
        )
        return None

    return payload if isinstance(payload, dict) else None


def _extract_direct_source_items(payload: dict | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []

    raw_items = payload.get("list")
    if raw_items is None:
        raw_items = payload.get("data")
    if raw_items is None:
        raw_items = payload.get("result")
    if not isinstance(raw_items, list):
        return []

    return [item for item in raw_items if isinstance(item, dict)]


def _merge_direct_source_details(
    feed_item: dict,
    descriptor: FeedDescriptor,
    source_details: list[dict],
) -> dict | None:
    if not source_details:
        return None

    merged_fields = {
        "vod_pic": "",
        "vod_remarks": "",
        "type_name": "",
        "vod_year": "",
        "vod_area": "",
        "vod_actor": "",
        "vod_director": "",
        "vod_content": "",
        "vod_score": "",
    }
    for detail in source_details:
        for field_name in merged_fields:
            if not merged_fields[field_name]:
                merged_fields[field_name] = str(detail.get(field_name, "") or "").strip()

    play_from_parts: list[str] = []
    play_url_parts: list[str] = []
    seen_parts: set[tuple[str, str]] = set()
    for detail in source_details:
        play_from = str(detail.get("vod_play_from", "") or "").strip()
        play_url = str(detail.get("vod_play_url", "") or "").strip()
        if not play_url:
            continue
        if not play_from:
            play_from = str(detail.get("_source_name", "") or "").strip()
        dedup_key = (play_from, play_url)
        if dedup_key in seen_parts:
            continue
        seen_parts.add(dedup_key)
        play_from_parts.append(play_from)
        play_url_parts.append(play_url)

    if not play_url_parts:
        return None

    first_detail = source_details[0]
    return {
        "vod_id": _build_direct_hot_tv_id(descriptor),
        "vod_name": str(first_detail.get("vod_name", "") or feed_item.get("title", "")).strip(),
        "vod_pic": merged_fields["vod_pic"],
        "vod_remarks": merged_fields["vod_remarks"],
        "type_name": merged_fields["type_name"],
        "vod_year": merged_fields["vod_year"],
        "vod_area": merged_fields["vod_area"],
        "vod_actor": merged_fields["vod_actor"],
        "vod_director": merged_fields["vod_director"],
        "vod_content": merged_fields["vod_content"],
        "vod_score": merged_fields["vod_score"],
        "source_count": len(play_url_parts),
        "vod_play_from": "$$$".join(play_from_parts),
        "vod_play_url": "$$$".join(play_url_parts),
    }


def _build_direct_hot_tv_id(descriptor: FeedDescriptor) -> str:
    digest = hashlib.sha1(descriptor.normalized_title.encode("utf-8")).hexdigest()[:12]
    return f"hot_tv_direct_{digest}"


def _build_detail_payload(item: VideoItem) -> dict:
    playable_sources = sorted(
        _playable_sources(item),
        key=lambda src: src.score,
        reverse=True,
    )
    play_from_parts = []
    play_url_parts = []

    for source in playable_sources:
        play_from_parts.append(f"{source.source_name}·{source.quality.value}")
        play_url_parts.append(source.to_play_string())

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
        "source_count": len(playable_sources),
        "vod_play_from": "$$$".join(play_from_parts),
        "vod_play_url": "$$$".join(play_url_parts),
    }
