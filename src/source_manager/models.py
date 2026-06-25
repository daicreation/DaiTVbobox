"""
Source Manager — 數據模型
定義 HealthScore, SourceScore, SourceRecord
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class HealthScore:
    """單次健康檢查結果"""
    source_key: str          # "bfzy"
    source_name: str         # "暴風"
    api_url: str             # "https://bfzyapi.com/api.php/provide/vod"
    checked_at: str = ""     # ISO 8601 時間戳

    # 五個維度（各 0-100）
    availability: float = 0       # API HEAD 請求是否可達
    response_time_ms: float = 0   # 平均響應時間（毫秒）
    search_success: float = 0     # 搜尋成功率（測試關鍵詞）
    detail_success: float = 0     # 詳情頁成功率
    play_success: float = 0       # 播放地址成功率

    # 加權總分
    health_score: float = 0

    def calculate(self, weights: dict):
        """
        根據權重計算 health_score

        預設權重:
          availability × 0.25
          + response_time_score × 0.15
          + search_success × 0.30
          + detail_success × 0.15
          + play_success × 0.15
        """
        # 響應時間轉分數：<500ms=100, <2000ms=70, <5000ms=40, >5000ms=10
        rt_score = 100 if self.response_time_ms < 500 else \
                   70 if self.response_time_ms < 2000 else \
                   40 if self.response_time_ms < 5000 else \
                   10 if self.response_time_ms > 0 else 0

        self.health_score = round(
            self.availability * weights.get("availability", 0.25)
            + rt_score * weights.get("response_time", 0.15)
            + self.search_success * weights.get("search_success", 0.30)
            + self.detail_success * weights.get("detail_success", 0.15)
            + self.play_success * weights.get("play_success", 0.15),
            1
        )
        return self.health_score


@dataclass
class SourceScore:
    """來源排名分數（基於多次健康檢查）"""
    source_key: str
    source_name: str
    score: float = 0           # 當前綜合評分 0-100
    updated_at: str = ""       # 最後更新時間

    # 歷史數據
    history_7d: list[float] = field(default_factory=list)
    trend: str = "stable"      # "up" / "stable" / "down"

    def update(self, new_health_score: float):
        """加入新的健康分數，更新趨勢"""
        self.history_7d.append(new_health_score)
        # 只保留最近 7 天
        if len(self.history_7d) > 14:  # 14 次 = 7天 × 每天2次
            self.history_7d = self.history_7d[-14:]

        # 計算平均
        self.score = round(sum(self.history_7d) / len(self.history_7d), 1)

        # 判斷趨勢
        if len(self.history_7d) >= 3:
            recent = self.history_7d[-3:]
            if recent[-1] > recent[0] + 3:
                self.trend = "up"
            elif recent[-1] < recent[0] - 3:
                self.trend = "down"
            else:
                self.trend = "stable"

        self.updated_at = datetime.now(timezone.utc).isoformat()


@dataclass
class SourceRecord:
    """來源資訊（從 config 解析）"""
    key: str
    name: str
    api: str
    type: str = "direct"  # "direct" | "config"
