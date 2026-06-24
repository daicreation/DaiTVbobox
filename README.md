# 📺 TVBox 影視聚合系統

**一鍵安裝、永久自動更新的 TVBox 影視聚合方案**

> 使用者只需在 TVBox 輸入 `https://tv.xxx.com`，永遠不需要手動更新。

---

## 🎯 核心特性

| 特性 | 說明 |
|------|------|
| 🔗 **單一入口** | 使用者只需一個網址，永遠不需更新 |
| ☁️ **Cloudflare Worker** | 全球 CDN 加速，隱藏 GitHub 真實地址 |
| 🤖 **每日自動更新** | GitHub Actions 每天自動抓取、測試、排序、發布 |
| 🎬 **4K 優先** | 自動識別 4K 資源並排在最前 |
| 📺 **平台分類** | 愛奇藝 / 騰訊 / 優酷 / 芒果 自動標記 |
| 🔢 **多源聚合** | 飯太硬 + 肥貓 + OK + 小蘋果 + 4K專用倉 (可擴展) |
| 📊 **智能評分** | 速度(25%) + 成功率(30%) + 穩定性(25%) + 畫質(20%) |
| 🔌 **可擴展** | 新增來源只需在 YAML 加一行配置 |

---

## 🏗️ 系統架構

```
使用者 (TVBox APK)
    │  輸入: https://tv.xxx.com
    ▼
Cloudflare Worker (反向代理)
    │  內部讀取 GitHub Repo
    ▼
GitHub Repo (公開但不直接暴露)
    │  config.json / movie.json / tv.json / variety.json / live.json
    │  spider.jar
    ▼
GitHub Actions (每日 08:00 自動執行)
    │  source_fetcher → health_checker → ranker → builder → publisher
    ▼
上游源 (飯太硬 / 肥貓 / OK / 小蘋果 / 4K專用倉)
```

---

## 🚀 快速部署

### 步驟 1: Fork 此 Repo

點擊右上角 **Fork** 按鈕，複製到你自己的 GitHub 帳號下。

### 步驟 2: 設定 GitHub Secrets

在 Repo → **Settings** → **Secrets and variables** → **Actions** 中新增：

| Secret | 說明 | 必須 |
|--------|------|------|
| `GH_PAT` | GitHub Personal Access Token (Repo 寫入權限) | ✅ 是 |
| `WORKER_DOMAIN` | 你的 Worker 域名 (如 `https://tv.yourname.com`) | 🟡 建議 |
| `CF_API_TOKEN` | Cloudflare API Token (清除快取用) | 🟢 可選 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token (失敗通知) | 🟢 可選 |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | 🟢 可選 |

### 步驟 3: 修改 Cloudflare Worker 配置

編輯 `worker/index.js`，修改以下兩行：

```javascript
const GITHUB_OWNER = 'your-github-username';    // 改為你的 GitHub ID
const WORKER_DOMAIN = 'https://tv.xxx.com';      // 改為你的域名
```

### 步驟 4: 部署 Cloudflare Worker

1. 登入 [Cloudflare Dashboard](https://dash.cloudflare.com)
2. 進入 **Workers & Pages** → **Create application**
3. 選擇 **Create Worker**
4. 貼上 `worker/index.js` 的全部內容
5. 點擊 **Save and Deploy**
6. (可選) 綁定自訂域名：**Triggers** → **Custom Domains**

### 步驟 5: 初始化 Repo

手動觸發一次 GitHub Actions：

1. 進入 Repo → **Actions**
2. 選擇 **📺 每日聚合更新**
3. 點擊 **Run workflow**

確認執行成功後，`output/` 目錄下會出現 JSON 檔案。

### 步驟 6: 安裝 TVBox

1. 下載 [Takagen99 TVBox](https://github.com/o0HalfLife0o/TVBoxOSC/releases) APK
2. 安裝到 Android TV / 手機 / 平板
3. 打開 TVBox → 右上角 **設定** → **配置地址**
4. 輸入 `https://tv.xxx.com` (你的 Worker 域名)
5. 確定 → 享受 🎉

---

## 📁 專案結構

```
tvbox-aggregator/
├── .github/workflows/daily-build.yml   # GitHub Actions 排程
├── config/
│   ├── sources.yaml                     # 上游源配置 (可擴展)
│   └── rules.yaml                       # 評分規則配置
├── src/
│   ├── source_fetcher.py                # ①: 來源抓取
│   ├── health_checker.py                # ②: 健康檢查
│   ├── ranker.py                        # ③: 評分排序
│   ├── builder.py                       # ④: JSON 生成
│   ├── publisher.py                     # ⑤: 發布提交
│   ├── utils.py                         # 共用工具
│   ├── models.py                        # 數據模型
│   └── constants.py                     # 常數定義
├── worker/index.js                      # Cloudflare Worker
├── output/                              # 最終 JSON (TVBox 讀取)
├── tests/                               # 單元測試
├── spider/                              # spider.jar
└── deploy/                              # 部署說明
```

---

## 🔧 擴展新來源

編輯 `config/sources.yaml`，新增一條配置：

```yaml
sources:
  # ... 原有配置 ...

  my_new_source:
    name: "新來源"
    url: "https://new-source.example.com/api"
    type: "json"
    category: ["movie", "tv"]
    quality_support: ["1080P", "720P"]
    priority: 3
    timeout: 30
    retry: 3
    enabled: true
```

無需修改任何程式碼！下次 Actions 執行時會自動抓取。

---

## 🧪 本機測試

```bash
# 安裝依賴
pip install -r requirements.txt

# 執行完整流程 (模擬 GitHub Actions)
cd repo
python -c "
from src.utils import setup_logging; setup_logging('INFO')
from src.source_fetcher import fetch_all_sources
from src.health_checker import check_all_sources
from src.ranker import rank_all_items
from src.builder import build_all_outputs
from src.utils import load_yaml
from src.constants import RULES_YAML_PATH
import pickle

rules = load_yaml(RULES_YAML_PATH)
caches = fetch_all_sources()
items = check_all_sources(caches, rules)
ranked = rank_all_items(items, rules)
paths = build_all_outputs(ranked, rules)
print('Done!')
"

# 執行測試
pytest tests/ -v
```

---

## 📊 評分公式

| 維度 | 權重 | 說明 |
|------|------|------|
| 速度 | 25% | 響應時間 < 0.5s → 100 分, > 10s → 0 分 |
| 成功率 | 30% | 最近 3 次 HEAD 測試的成功比例 |
| 穩定性 | 25% | 多次測試的響應時間方差 |
| 畫質 | 20% | 4K:+100, 1080P:+70, 720P:+40 |

**總分 = 速度×0.25 + 成功率×0.30 + 穩定性×0.25 + 畫質×0.20**

---

## ⚠️ 注意事項

1. **上游源可能失效** — 需要定期更新 `sources.yaml` 中的 URL
2. **中國大陸網路** — 直接訪問 Cloudflare Worker 可能較慢，可考慮使用優選 IP
3. **版權** — 本系統僅做聚合，**不存儲任何影片內容**
4. **GitHub Actions 免費額度** — 公開 Repo 每月 2000 分鐘，本專案每天執行約 3-5 分鐘，完全足夠
5. **Cloudflare Worker 免費額度** — 每日 10 萬請求，個人使用完全足夠

---

## 📄 License

MIT License — 自由使用、修改、分發。
