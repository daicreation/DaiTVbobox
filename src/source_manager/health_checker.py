"""
Source Manager — 健康檢查
測試每個來源 API 的可用性、速度、搜尋、詳情、播放
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import HealthScore
from ..utils import logger

# 搜尋測試關鍵詞（熱門 + 冷門混合，確保公平）
TEST_KEYWORDS = ["铁拳", "狂飙", "开端", "庆余年", "半熟恋人"]

# 分數權重
DEFAULT_WEIGHTS = {
    "availability": 0.25,
    "response_time": 0.15,
    "search_success": 0.30,
    "detail_success": 0.15,
    "play_success": 0.15,
}


def test_single_source(source: dict, weights: dict = None) -> HealthScore:
    """
    測試單個來源

    Args:
        source: {"key": "bfzy", "name": "暴風", "api": "https://...", "type": "direct"}
        weights: 評分權重 dict

    Returns:
        HealthScore 物件
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    hs = HealthScore(
        source_key=source.get("key", ""),
        source_name=source.get("name", ""),
        api_url=source.get("api", ""),
        checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )

    api_url = source.get("api", "")
    if not api_url:
        return hs

    import httpx

    try:
        client = httpx.Client(timeout=10, follow_redirects=True)
        base_url = api_url.rstrip("/")

        # 1. Availability — HEAD 請求
        try:
            start = time.time()
            r = client.head(base_url)
            elapsed_ms = (time.time() - start) * 1000
            if r.status_code < 500:
                hs.availability = 100
                hs.response_time_ms = elapsed_ms
        except Exception:
            hs.availability = 0

        # 2. Search Success — 測試搜尋關鍵詞
        search_ok = 0
        for kw in TEST_KEYWORDS[:3]:  # 只測 3 個，節省時間
            try:
                r = client.get(f"{base_url}?ac=detail&wd={kw}", timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("list") and len(data["list"]) > 0:
                        search_ok += 1
            except Exception:
                pass
        hs.search_success = (search_ok / 3) * 100

        # 3. Detail Success — 取第一筆搜尋結果查詳情
        detail_ok = 0
        try:
            r = client.get(f"{base_url}?ac=detail&wd={TEST_KEYWORDS[0]}", timeout=8)
            if r.status_code == 200:
                data = r.json()
                items = data.get("list", [])
                if items:
                    vod_id = items[0].get("vod_id", "")
                    if vod_id:
                        r2 = client.get(f"{base_url}?ac=videolist&ids={vod_id}", timeout=8)
                        if r2.status_code == 200 and len(r2.text) > 100:
                            detail_ok = 1
        except Exception:
            pass
        hs.detail_success = detail_ok * 100

        # 4. Play Success — HEAD 檢查 m3u8 播放地址
        play_ok = 0
        try:
            r = client.get(f"{base_url}?ac=detail&wd={TEST_KEYWORDS[0]}", timeout=8)
            if r.status_code == 200:
                data = r.json()
                items = data.get("list", [])
                for item in items[:2]:  # 只測前 2 筆
                    play_url = item.get("vod_play_url", "")
                    urls = [u.split("$")[-1] for u in play_url.split("#") if "$" in u]
                    for u in urls[:2]:  # 每筆測前 2 集
                        try:
                            r2 = client.head(u, timeout=5)
                            if r2.status_code < 500:
                                play_ok += 1
                                break
                        except Exception:
                            pass
        except Exception:
            pass
        hs.play_success = min(100, (play_ok / 2) * 100)

        client.close()
    except Exception as e:
        logger.warning(f"Health check error for {source.get('name','?')}: {e}")

    hs.calculate(weights)
    return hs


def check_all_sources(sources: list[dict], workers: int = 3) -> list[HealthScore]:
    """
    並行測試所有來源

    Args:
        sources: 來源列表
        workers: 並行數

    Returns:
        HealthScore 列表
    """
    results = []
    total = len(sources)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(test_single_source, s): s for s in sources}
        for i, future in enumerate(as_completed(futures), 1):
            src = futures[future]
            try:
                hs = future.result()
                results.append(hs)
                logger.info(f"[{i}/{total}] {hs.source_name}: score={hs.health_score} "
                           f"(avail={hs.availability}, search={hs.search_success}, "
                           f"detail={hs.detail_success}, play={hs.play_success})")
            except Exception as e:
                logger.error(f"[{i}/{total}] {src.get('name','?')}: FAILED - {e}")

    results.sort(key=lambda x: x.health_score, reverse=True)
    return results
