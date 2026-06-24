# ============================================================
# TVBox 影視聚合系統 — 數據模型
# 使用 Python dataclass 定義所有核心資料結構
# 確保型別安全、易於序列化、方便單元測試
# ============================================================

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Quality(Enum):
    """
    畫質等級枚舉

    排序規則：4K > 1080P > 720P > 480P > 未知
    """
    K4 = "4K"
    K1080 = "1080P"
    K720 = "720P"
    K480 = "480P"
    UNKNOWN = "未知"

    @classmethod
    def from_string(cls, text: str) -> "Quality":
        """
        從字串解析畫質等級
        支援各種可能的表示方式：4K / 2160P / UHD → K4
        """
        text = text.upper().strip()
        if text in ("4K", "2160P", "UHD", "4K·", "·4K"):
            return cls.K4
        if text in ("1080P", "1080", "FHD", "BLURAY"):
            return cls.K1080
        if text in ("720P", "720", "HD"):
            return cls.K720
        if text in ("480P", "480", "SD"):
            return cls.K480
        return cls.UNKNOWN

    def sort_order(self) -> int:
        """用於排序：數字越小畫質越高"""
        order = {Quality.K4: 0, Quality.K1080: 1, Quality.K720: 2, Quality.K480: 3, Quality.UNKNOWN: 4}
        return order.get(self, 4)


class Category(Enum):
    """
    內容類別枚舉
    對應 output/ 下的 JSON 檔案
    """
    MOVIE = "movie"
    TV = "tv"
    VARIETY = "variety"
    LIVE = "live"

    @classmethod
    def from_string(cls, text: str) -> "Category":
        """從字串解析類別"""
        text = text.lower().strip()
        mapping = {
            "movie": cls.MOVIE, "電影": cls.MOVIE, "电影": cls.MOVIE,
            "tv": cls.TV, "電視劇": cls.TV, "电视剧": cls.TV, "剧集": cls.TV,
            "variety": cls.VARIETY, "綜藝": cls.VARIETY, "综艺": cls.VARIETY,
            "live": cls.LIVE, "直播": cls.LIVE,
        }
        return mapping.get(text, cls.MOVIE)


@dataclass
class PlaySource:
    """
    單個播放來源

    代表一個影片在某個來源（飯太硬/肥貓/...）的播放連結
    包含健康檢查後的各項指標
    """
    url: str                                    # 播放 URL
    source_name: str                            # 來源名稱（例："飯太硬"）
    quality: Quality = Quality.UNKNOWN           # 畫質等級
    response_time: float = 0.0                  # 響應時間 (秒)
    success_rate: float = 0.0                   # 成功率 (0.0 ~ 1.0)
    stability: float = 0.0                      # 穩定性分數 (0.0 ~ 100.0)
    speed_score: float = 0.0                    # 速度分數 (0.0 ~ 100.0)
    quality_score: float = 0.0                  # 畫質分數 (0.0 ~ 100.0)
    score: float = 0.0                          # 綜合評分 (0.0 ~ 100.0)
    last_checked: str = ""                      # 最後檢查時間 (ISO 8601)
    is_available: bool = True                   # 當前是否可用
    http_status: int = 200                      # HTTP 狀態碼
    episode_name: str = "第1集"                 # 集數名稱
    extra: dict = field(default_factory=dict)   # 額外資訊（可擴展）

    def to_play_string(self) -> str:
        """
        轉換為 TVBox 播放格式
        例：第1集$https://example.com/play
        """
        return f"{self.episode_name}{'$'}{self.url}"


@dataclass
class VideoItem:
    """
    影片項目

    代表一部電影 / 電視劇 / 綜藝節目
    可能來自多個上游源，合併後包含多個 PlaySource
    """
    vod_id: str                                         # 唯一識別碼
    vod_name: str                                       # 影片名稱
    vod_pic: str = ""                                   # 海報圖片 URL
    vod_remarks: str = ""                               # 備註（顯示在列表）
    type_name: str = ""                                 # 分類（動作/喜劇/...）
    vod_year: str = ""                                  # 年份
    vod_area: str = ""                                  # 地區
    vod_actor: str = ""                                 # 演員
    vod_director: str = ""                              # 導演
    vod_content: str = ""                               # 簡介
    vod_score: str = ""                                 # 豆瓣/IMDB 評分
    category: Category = Category.MOVIE                 # 內容類別
    platform: str = ""                                  # 平台（愛奇藝/騰訊/優酷/芒果）
    episode_count: int = 0                              # 總集數（電視劇）
    episode_updated: int = 0                            # 已更新集數（電視劇）
    sources: list[PlaySource] = field(default_factory=list)  # 播放來源列表

    def best_quality(self) -> Quality:
        """返回所有來源中最好的畫質"""
        if not self.sources:
            return Quality.UNKNOWN
        return min(
            (s.quality for s in self.sources),
            key=lambda q: q.sort_order(),
            default=Quality.UNKNOWN,
        )

    def best_source_name(self) -> str:
        """返回評分最高的來源名稱"""
        if not self.sources:
            return "未知"
        return max(self.sources, key=lambda s: s.score).source_name

    def to_tvbox_dict(self) -> dict:
        """
        轉換為 TVBox JSON 格式的 dict
        包含 vod_play_from 與 vod_play_url
        """
        # 按評分降序排列來源
        sorted_sources = sorted(
            [s for s in self.sources if s.is_available and s.score > 0],
            key=lambda s: s.score,
            reverse=True,
        )

        # 生成 vod_play_from：各線路的名稱
        # 格式："飯太硬·4K$$$肥貓·1080P$$$OK·720P"
        play_from_parts = []
        play_url_parts = []

        for src in sorted_sources:
            play_from_parts.append(f"{src.source_name}·{src.quality.value}")
            play_url_parts.append(src.to_play_string())

        vod_play_from = "$$$".join(play_from_parts)
        vod_play_url = "#".join(play_url_parts)

        return {
            "vod_id": self.vod_id,
            "vod_name": self.vod_name,
            "vod_pic": self.vod_pic,
            "vod_remarks": self.vod_remarks,
            "type_name": self.type_name,
            "vod_year": self.vod_year,
            "vod_area": self.vod_area,
            "vod_actor": self.vod_actor,
            "vod_director": self.vod_director,
            "vod_content": self.vod_content,
            "vod_score": self.vod_score,
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url,
            "vod_quality": self.best_quality().value,
            "source_count": len(sorted_sources),
            "source_rank": int(
                sum(s.score for s in sorted_sources) / max(len(sorted_sources), 1)
            ),
        }


@dataclass
class HealthCheckResult:
    """
    健康檢查結果

    記錄一個播放 URL 的可用性測試結果
    """
    url: str                            # 被測試的 URL
    source_name: str                    # 來源名稱
    is_available: bool = False          # 是否可用
    http_status: int = 0                # HTTP 狀態碼
    response_time: float = 0.0          # 響應時間 (秒)
    content_length: int = 0             # 內容長度 (bytes)
    content_type: str = ""              # Content-Type
    error_message: str = ""             # 錯誤訊息
    checked_at: str = ""                # 檢查時間
    attempt: int = 1                    # 第幾次嘗試


@dataclass
class SourceCache:
    """
    來源快取

    記錄對一個上游源的抓取結果，用於下次比對
    """
    source_key: str                     # 來源識別碼 (fantaiying / feimao / ...)
    source_name: str                    # 來源名稱
    fetched_at: str                     # 抓取時間
    item_count: int = 0                 # 影片數量
    raw_size: int = 0                   # 原始數據大小 (bytes)
    items: list[dict] = field(default_factory=list)  # 影片列表 (dict 格式)
