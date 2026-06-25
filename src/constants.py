# ============================================================
# TVBox 影視聚合系統 — 常數定義
# 所有固定值集中在這裡，方便統一管理與修改
# 與 config/*.yaml 配合使用，這裡存放程式層級的常數
# ============================================================

import os
from pathlib import Path

# ---- 專案根目錄 ----
# 自動偵測：GitHub Actions 環境 vs 本機開發環境
ROOT_DIR = Path(os.environ.get("GITHUB_WORKSPACE", Path(__file__).resolve().parent.parent))

# ---- 子目錄路徑 ----
CONFIG_DIR = ROOT_DIR / "config"
OUTPUT_DIR = ROOT_DIR / "output"
SOURCES_DIR = ROOT_DIR / "sources"      # 存放原始抓取數據的目錄
CACHE_DIR = ROOT_DIR / "cache"          # 存放健康檢查快取的目錄
LOGS_DIR = ROOT_DIR / "logs"            # 存放執行日誌的目錄
SPIDER_DIR = ROOT_DIR / "spider"        # spider.jar 目錄

# ---- 配置檔案路徑 ----
SOURCES_YAML_PATH = CONFIG_DIR / "sources.yaml"
RULES_YAML_PATH = CONFIG_DIR / "rules.yaml"

# ---- 輸出 JSON 路徑 (TVBox 讀取的檔案) ----
OUTPUT_CONFIG_JSON = OUTPUT_DIR / "config.json"
OUTPUT_CONFIG_HK_JSON = OUTPUT_DIR / "config.hk.json"
OUTPUT_CONFIG_CN_JSON = OUTPUT_DIR / "config.cn.json"
OUTPUT_MOVIE_JSON = OUTPUT_DIR / "movie.json"
OUTPUT_TV_JSON = OUTPUT_DIR / "tv.json"
OUTPUT_VARIETY_JSON = OUTPUT_DIR / "variety.json"
OUTPUT_LIVE_JSON = OUTPUT_DIR / "live.json"

# ---- GitHub Repo 資訊 (從環境變數讀取，確保安全) ----
GITHUB_REPO_OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "daicreation")
GITHUB_REPO_NAME = os.environ.get("GITHUB_REPOSITORY", "daicreation/DaiTVbobox")
# Raw URL 模板: Worker 內部使用，不直接暴露給使用者
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO_NAME}/main"

# ---- Cloudflare Worker 資訊 ----
# 使用者看到的唯一入口
WORKER_DOMAIN = os.environ.get("WORKER_DOMAIN", "https://tv.xxx.com")
# 如果你有自訂域名，修改上面的環境變數或直接改這裡

# ---- HTTP 請求設定 ----
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 11; TV) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# ---- 默認請求參數 ----
DEFAULT_TIMEOUT = 30          # 預設 HTTP 超時 (秒)
DEFAULT_RETRY = 3             # 預設重試次數
DEFAULT_RETRY_DELAY = 2       # 重試間隔 (秒)
MAX_CONCURRENT_FETCHES = 5    # 最大並行抓取數

# ---- 類別定義 ----
# 每個類別的 type_id 與顯示名稱
CATEGORIES = {
    "movie": {
        "name": "電影",
        "output_file": OUTPUT_MOVIE_JSON,
        "type_id_prefix": "movie",
    },
    "tv": {
        "name": "電視劇",
        "output_file": OUTPUT_TV_JSON,
        "type_id_prefix": "tv",
    },
    "variety": {
        "name": "綜藝",
        "output_file": OUTPUT_VARIETY_JSON,
        "type_id_prefix": "variety",
    },
    "live": {
        "name": "直播",
        "output_file": OUTPUT_LIVE_JSON,
        "type_id_prefix": "live",
    },
}

# ---- 畫質定義 (從高到低排序) ----
QUALITY_ORDER = ["4K", "1080P", "720P", "480P", "未知"]

# ---- TVBox JSON 格式常數 ----
# 每個分類的預設 JSON 結構
TVBOX_CLASSES = {
    "movie": [
        {"type_name": "全部", "type_id": "0"},
        {"type_name": "動作", "type_id": "1"},
        {"type_name": "喜劇", "type_id": "2"},
        {"type_name": "科幻", "type_id": "3"},
        {"type_name": "恐怖", "type_id": "4"},
        {"type_name": "劇情", "type_id": "5"},
        {"type_name": "動畫", "type_id": "6"},
        {"type_name": "紀錄片", "type_id": "7"},
        {"type_name": "4K專區", "type_id": "99"},
    ],
    "tv": [
        {"type_name": "全部", "type_id": "0"},
        {"type_name": "國產劇", "type_id": "1"},
        {"type_name": "港台劇", "type_id": "2"},
        {"type_name": "日韓劇", "type_id": "3"},
        {"type_name": "歐美劇", "type_id": "4"},
        {"type_name": "愛奇藝", "type_id": "10"},
        {"type_name": "騰訊", "type_id": "11"},
        {"type_name": "優酷", "type_id": "12"},
        {"type_name": "芒果", "type_id": "13"},
    ],
    "variety": [
        {"type_name": "全部", "type_id": "0"},
        {"type_name": "內地綜藝", "type_id": "1"},
        {"type_name": "港台綜藝", "type_id": "2"},
        {"type_name": "日韓綜藝", "type_id": "3"},
        {"type_name": "歐美綜藝", "type_id": "4"},
    ],
    "live": [
        {"type_name": "央視", "type_id": "cctv"},
        {"type_name": "衛視", "type_id": "satellite"},
        {"type_name": "地方", "type_id": "local"},
        {"type_name": "體育", "type_id": "sports"},
        {"type_name": "電影", "type_id": "movie"},
        {"type_name": "4K", "type_id": "4k"},
    ],
}

# ---- TVBox 播放線路分隔符 ----
# TVBox 使用 "$$$" 分隔不同播放線路
# 使用 "#" 分隔每一集
# 使用 "$" 分隔集數名稱與 URL
# 格式: "線路1·1080P$$$線路2·720P" / "第1集$url1#第2集$url2"
PLAY_FROM_SEPARATOR = "$$$"    # 線路之間的分隔符
PLAY_URL_SEPARATOR = "#"       # 集數之間的分隔符
EPISODE_URL_SEPARATOR = "$"    # 集數名與 URL 的分隔符
