"""Chill-AI-TV — Builder: 從抓取結果生成 config.json"""
from .constants import OUTPUT_DIR
from .utils import save_json, now_display

# 精選核心站點（品牌 + 已驗證可用，永遠在最前面）
CORE_SITES = [
    {"key": "bfzy", "name": "🧊 Chill-TV", "type": 1, "api": "https://daitvbobox.chungshare.workers.dev/api", "searchable": 1, "quickSearch": 1},
    {"key": "ff",         "name": "⚡ 非凡",        "type": 1, "api": "http://cj.ffzyapi.com/api.php/provide/vod", "searchable": 1, "quickSearch": 1},
    {"key": "sn",         "name": "🎯 索尼",        "type": 1, "api": "https://suoniapi.com/api.php/provide/vod", "searchable": 1, "quickSearch": 1},
    {"key": "lz",         "name": "🔮 量子",        "type": 1, "api": "https://cj.lziapi.com/api.php/provide/vod/", "searchable": 1, "quickSearch": 1},
    {"key": "360",        "name": "💠 360",         "type": 1, "api": "https://360zyzz.com/api.php/provide/vod/", "searchable": 1, "quickSearch": 1},
    {"key": "js",         "name": "⚡ 極速",        "type": 1, "api": "https://jszyapi.com/api.php/provide/vod/", "searchable": 1, "quickSearch": 1},
    {"key": "jy",         "name": "🦅 金鷹",        "type": 1, "api": "https://jyzyapi.com/provide/vod/", "searchable": 1, "quickSearch": 1},
    {"key": "xiaosa",     "name": "💨 瀟灑",        "type": 1, "api": "https://qist.wyfc.qzz.io/xiaosa/api.json", "searchable": 1, "quickSearch": 1},
    {"key": "xiaopingguo","name": "🍎 小蘋果",      "type": 1, "api": "https://bitbucket.org/xduo/duoapi/raw/master/xpg.json", "searchable": 1, "quickSearch": 1},
    {"key": "moyuer",     "name": "🐟 摸魚兒",      "type": 1, "api": "https://6800.kstore.vip/fish.json", "searchable": 1, "quickSearch": 1},
    {"key": "fantaiying", "name": "🍚 飯太硬",      "type": 1, "api": "https://qist.wyfc.qzz.io/fty.json", "searchable": 1, "quickSearch": 1},
]

def build_all_outputs(all_items=None, rules_config=None, domain=""):
    """核心站點固定 + 自動發現的新站追加"""
    sites = list(CORE_SITES)
    core_apis = {s["api"] for s in CORE_SITES}

    if all_items:
        for items in all_items.values():
            for item in items:
                if item.type_name == "站點" and item.sources:
                    src = item.sources[0]
                    if src.url and src.url.startswith("http") and src.is_available:
                        if src.url not in core_apis:
                            name = item.vod_name.replace("[站點] ", "").replace("[直播] ", "")
                            key = "auto_" + (name[:8] or "site")
                            core_apis.add(src.url)
                            sites.append({
                                "key": key, "name": name, "type": 1,
                                "api": src.url, "searchable": 1, "quickSearch": 1,
                            })

    config = {
        "sites": sites,
        "flags": ["4K","1080P","720P","優酷","愛奇藝","騰訊","芒果"],
        "update_time": now_display(),
    }

    path = OUTPUT_DIR / "config.json"
    save_json(config, path)
    return {"config": path}
