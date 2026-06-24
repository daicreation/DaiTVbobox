# ============================================================
# TVBox 影視聚合系統 — 共用工具函數
# 提供 HTTP 請求封裝、日誌、JSON 處理、字串比對等功能
# 所有模組都依賴此模組
# ============================================================

import gzip
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

import httpx
import yaml
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .constants import (
    HTTP_HEADERS,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY,
    DEFAULT_RETRY_DELAY,
    LOGS_DIR,
)

# ---- 日誌設定 ----
def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    設定結構化日誌
    輸出到控制台 + 檔案

    Args:
        level: 日誌等級 (DEBUG / INFO / WARNING / ERROR)

    Returns:
        設定好的 Logger 實例
    """
    logger = logging.getLogger("tvbox_aggregator")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重複添加 handler
    if logger.handlers:
        return logger

    # 控制台輸出格式
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # 檔案輸出格式 (保存到 logs/ 目錄)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    file_handler = logging.FileHandler(
        LOGS_DIR / f"build_{today}.log", encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s [%(funcName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger


# 全局 logger 實例
logger = logging.getLogger("tvbox_aggregator")


# ---- YAML 配置讀取 ----
def load_yaml(file_path: Path) -> dict:
    """
    讀取 YAML 配置文件

    Args:
        file_path: YAML 檔案路徑

    Returns:
        解析後的 dict，讀取失敗時返回空 dict

    Usage:
        config = load_yaml(Path("config/sources.yaml"))
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            logger.info(f"已讀取配置: {file_path.name}")
            return data or {}
    except FileNotFoundError:
        logger.error(f"配置文件不存在: {file_path}")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"YAML 解析錯誤 ({file_path.name}): {e}")
        return {}


def save_json(data: Any, file_path: Path, compress: bool = False) -> bool:
    """
    將數據寫入 JSON 檔案

    Args:
        data: 要寫入的數據 (dict / list)
        file_path: 目標檔案路徑
        compress: 是否壓縮 (去除空白)

    Returns:
        寫入成功返回 True

    Usage:
        save_json(movie_data, Path("output/movie.json"))
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            if compress:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            else:
                json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"已寫入 JSON: {file_path.name} ({file_path.stat().st_size:,} bytes)")
        return True
    except (OSError, TypeError) as e:
        logger.error(f"寫入 JSON 失敗 ({file_path.name}): {e}")
        return False


def load_json(file_path: Path) -> Optional[dict]:
    """
    安全讀取 JSON 檔案

    Args:
        file_path: JSON 檔案路徑

    Returns:
        解析後的 dict，失敗返回 None
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"讀取 JSON 失敗 ({file_path.name}): {e}")
        return None


# ---- HTTP 請求封裝 (含重試) ----
def create_http_client(timeout: int = DEFAULT_TIMEOUT) -> httpx.Client:
    """
    建立統一的 HTTP 客戶端

    Args:
        timeout: 請求超時 (秒)

    Returns:
        設定好的 httpx.Client 實例
    """
    return httpx.Client(
        headers=HTTP_HEADERS,
        timeout=httpx.Timeout(timeout),
        follow_redirects=True,          # 自動跟隨重定向
        http2=False,                    # 關閉 HTTP/2 (避免 h2 依賴問題)
        limits=httpx.Limits(
            max_keepalive_connections=10,
            max_connections=20,
        ),
    )


@retry(
    stop=stop_after_attempt(DEFAULT_RETRY),
    wait=wait_exponential(multiplier=1, min=DEFAULT_RETRY_DELAY, max=10),
    retry=retry_if_exception_type(
        (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)
    ),
)
def http_get(
    url: str,
    client: Optional[httpx.Client] = None,
    timeout: int = DEFAULT_TIMEOUT,
    encoding: str = "utf-8",
) -> Optional[str]:
    """
    執行 HTTP GET 請求 (含自動重試)

    使用 tenacity 實現指數退避重試：
    - 第 1 次重試：等待 2 秒
    - 第 2 次重試：等待 4 秒
    - 第 3 次重試：等待 8 秒

    Args:
        url: 請求 URL
        client: HTTP 客戶端 (可重複使用)
        timeout: 超時時間 (秒)
        encoding: 回應編碼

    Returns:
        回應內容字串，失敗返回 None

    Usage:
        html = http_get("http://饭太硬.com/tv")
    """
    should_close = client is None
    if client is None:
        client = create_http_client(timeout)

    try:
        logger.debug(f"HTTP GET: {url}")
        start = time.time()
        response = client.get(url)
        elapsed = time.time() - start

        response.raise_for_status()

        # 處理 gzip 壓縮
        content = response.text

        logger.debug(f"HTTP {response.status_code} ({elapsed:.2f}s) {len(content):,} bytes <- {url}")
        return content

    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP {e.response.status_code}: {url}")
        raise  # 觸發 tenacity 重試
    except Exception as e:
        logger.warning(f"HTTP 請求失敗: {type(e).__name__}: {e} | {url}")
        raise
    finally:
        if should_close and client is not None:
            client.close()


def http_head_check(
    url: str,
    client: Optional[httpx.Client] = None,
    timeout: int = 10,
) -> dict:
    """
    執行 HTTP HEAD 請求檢查 URL 可用性

    使用 HEAD 方法只取回應頭，不下載內容，節省頻寬

    Args:
        url: 要檢查的 URL
        client: HTTP 客戶端
        timeout: 超時時間 (秒)

    Returns:
        {
            "status": HTTP 狀態碼,
            "response_time": 響應時間 (秒),
            "content_type": Content-Type,
            "content_length": 內容長度 (bytes),
            "error": 錯誤訊息 (成功時為 None),
        }
    """
    result = {
        "status": 0,
        "response_time": 0.0,
        "content_type": "",
        "content_length": 0,
        "error": None,
    }

    should_close = client is None
    if client is None:
        client = create_http_client(timeout)

    try:
        start = time.time()
        response = client.head(url)
        elapsed = time.time() - start

        result["status"] = response.status_code
        result["response_time"] = round(elapsed, 3)
        result["content_type"] = response.headers.get("Content-Type", "")
        cl = response.headers.get("Content-Length", "0")
        try:
            result["content_length"] = int(cl)
        except ValueError:
            result["content_length"] = 0

    except httpx.TimeoutException:
        result["error"] = "timeout"
    except httpx.NetworkError as e:
        result["error"] = f"network: {e}"
    except Exception as e:
        result["error"] = str(e)[:200]
    finally:
        if should_close and client is not None:
            client.close()

    return result


# ---- 文字處理工具 ----
def normalize_title(title: str) -> str:
    """
    正規化影片標題，用於去重比對

    處理步驟：
    1. 轉小寫
    2. 去除年份差異 (2025) 2025
    3. 去除括號內容 (含中英文括號)
    4. 去除多餘空白
    5. 去除常見後綴 (HD / 4K / 1080P)

    Args:
        title: 原始標題

    Returns:
        正規化後的標題

    Examples:
        normalize_title("範例電影 (2025) 4K") → "範例電影"
        normalize_title("Example Movie [HD]") → "example movie"
    """
    if not title:
        return ""

    # 轉小寫
    result = title.lower().strip()

    # 去除括號內容: (xxx) [xxx] （xxx）
    result = re.sub(r'\([^)]*\)', '', result)
    result = re.sub(r'\[[^\]]*\]', '', result)
    result = re.sub(r'（[^）]*）', '', result)

    # 去除年份
    result = re.sub(r'\b(19|20)\d{2}\b', '', result)

    # 去除常見畫質/版本標記
    result = re.sub(r'\b(4k|2160p|1080p|720p|480p|hd|bd|hdr|uhd)\b', '', result)

    # 去除多餘空白
    result = re.sub(r'\s+', ' ', result).strip()

    # 去除前後的標點符號
    result = result.strip(' -–—·,，。')

    return result


def levenshtein_ratio(s1: str, s2: str) -> float:
    """
    計算兩個字串的 Levenshtein 相似度

    使用 python-Levenshtein 庫進行高效計算
    返回 0.0 ~ 1.0 的相似度比例

    Args:
        s1: 字串 1
        s2: 字串 2

    Returns:
        相似度 (0.0 = 完全不同, 1.0 = 完全相同)

    Examples:
        levenshtein_ratio("範例電影", "範例電影2025") → ~0.8
    """
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    try:
        import Levenshtein
        return Levenshtein.ratio(s1, s2)
    except ImportError:
        # Fallback: 純 Python 實現 (較慢但無依賴)
        return _simple_levenshtein_ratio(s1, s2)


def _simple_levenshtein_ratio(s1: str, s2: str) -> float:
    """
    純 Python Levenshtein 距離實現 (fallback)

    當 python-Levenshtein 庫不可用時使用
    """
    if len(s1) < len(s2):
        s1, s2 = s2, s1

    if len(s2) == 0:
        return 0.0

    # 只取前 100 個字元比較，避免過長字串
    s1 = s1[:200]
    s2 = s2[:200]

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # 插入/刪除/替換的開銷
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    distance = previous_row[-1]
    max_len = max(len(s1), len(s2))
    return 1.0 - (distance / max_len)


def detect_platform(text: str, platform_map: dict) -> str:
    """
    從文字中檢測影片平台

    用於電視劇分類（愛奇藝/騰訊/優酷/芒果）

    Args:
        text: 要檢測的文字（標題 + 來源名稱 + 備註）
        platform_map: 平台關鍵字映射 (來自 rules.yaml)

    Returns:
        平台名稱，未檢測到返回空字串

    Example:
        detect_platform("某劇·愛奇藝", platform_map) → "愛奇藝"
    """
    if not text:
        return ""

    text_lower = text.lower()

    for key, config in platform_map.items():
        keywords = config.get("keywords", [])
        for kw in keywords:
            if kw.lower() in text_lower:
                return config.get("name", key)

    return ""


def parse_episode_info(text: str) -> tuple[int, int]:
    """
    解析電視劇的集數資訊

    支援多種格式：
    - "更新至24集" → (0, 24)
    - "40集全" → (40, 40)
    - "更新至第8集/共40集" → (40, 8)

    Args:
        text: 包含集數資訊的文字

    Returns:
        (總集數, 已更新集數)
    """
    total = 0
    updated = 0

    # 匹配 "共40集" / "全40集" / "40集全"
    total_match = re.search(r'(?:共|全)\s*(\d+)\s*集|(\d+)\s*集\s*全', text)
    if total_match:
        total = int(total_match.group(1) or total_match.group(2))

    # 匹配 "更新至24集" / "更新到第8集"
    updated_match = re.search(r'(?:更新[至到]|已更?至?)\s*(?:第)?\s*(\d+)\s*集', text)
    if updated_match:
        updated = int(updated_match.group(1))

    # 如果沒有找到更新資訊，但找到了總集數，且標記為"全"，則更新 = 總集數
    if updated == 0 and total > 0:
        if "全" in text or "完结" in text or "完結" in text:
            updated = total

    return total, updated


# ---- 時間處理 ----
def now_iso() -> str:
    """取得當前時間 ISO 8601 格式字串"""
    return datetime.now(timezone.utc).isoformat()


def now_display(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """取得當前時間的顯示格式字串"""
    return datetime.now().strftime(fmt)


# ---- 資料結構工具 ----
def chunk_list(data: list, size: int) -> list[list]:
    """
    將大列表切割為小批次

    用於大量 URL 的批次健康檢查，避免一次性發送過多請求

    Args:
        data: 原始列表
        size: 每批大小

    Returns:
        二維列表 [ [batch1], [batch2], ... ]

    Example:
        chunk_list([1,2,3,4,5], 2) → [[1,2], [3,4], [5]]
    """
    return [data[i : i + size] for i in range(0, len(data), size)]


def safe_get(d: dict, *keys, default=None):
    """
    安全從巢狀 dict 中取值

    Args:
        d: 目標 dict
        *keys: 鍵路徑
        default: 找不到時的預設值

    Example:
        safe_get(data, "site", "name") → data["site"]["name"]
    """
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d
