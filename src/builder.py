"""
Chill-AI-TV — Builder: 生成 TVBox config.json
只放配置源，TVBox 用自己的 IP 直連
"""
from .constants import OUTPUT_DIR
from .utils import save_json, now_display

def build_all_outputs(all_items=None, rules_config=None, domain="https://daitvbobox.chungshare.workers.dev"):
    """生成所有輸出 JSON"""
    config_path = _build_config_json(domain)
    return {"config": config_path}

def _build_config_json(domain: str):
    """生成 config.json — 多站點直連（像寶盒）"""

    config = {
        "sites": [
            {"key": "bfzy",      "name": "🔥 暴風",     "type": 1, "api": "https://bfzyapi.com/api.php/provide/vod",        "searchable": 1, "quickSearch": 1},
            {"key": "hwk",       "name": "🌏 海外看",   "type": 1, "api": "https://haiwaikan.com/api.php/provide/vod",      "searchable": 1, "quickSearch": 1},
            {"key": "ff",        "name": "⚡ 非凡",      "type": 1, "api": "http://cj.ffzyapi.com/api.php/provide/vod",       "searchable": 1, "quickSearch": 1},
            {"key": "sn",        "name": "🎯 索尼",      "type": 1, "api": "https://suoniapi.com/api.php/provide/vod",        "searchable": 1, "quickSearch": 1},
            {"key": "fantaiying","name": "🍚 飯太硬",   "type": 1, "api": "https://qist.wyfc.qzz.io/fty.json",               "searchable": 1, "quickSearch": 1},
            {"key": "xiaosa",    "name": "💨 瀟灑",     "type": 1, "api": "https://qist.wyfc.qzz.io/xiaosa/api.json",       "searchable": 1, "quickSearch": 1},
            {"key": "liu",       "name": "📦 liu673cn", "type": 1, "api": "https://cdn.jsdelivr.net/gh/liu673cn/box@main/m.json", "searchable": 1, "quickSearch": 1},
            {"key": "moyuer",    "name": "🐟 摸魚兒",   "type": 1, "api": "https://6800.kstore.vip/fish.json",              "searchable": 1, "quickSearch": 1},
            {"key": "feimao",    "name": "🐱 肥貓",     "type": 1, "api": "http://feimao.pro",                               "searchable": 1, "quickSearch": 1},
            {"key": "ok",        "name": "👌 OK",        "type": 1, "api": "https://gist.githubusercontent.com/ph7368/20ee6c7b64d77d82f8f4162cdd04ad61/raw/gistfile1.txt", "searchable": 1, "quickSearch": 1},
            {"key": "wangerxiao","name": "👦 王二小",   "type": 1, "api": "https://9280.kstore.vip/newwex.json",             "searchable": 1, "quickSearch": 1},
            {"key": "xiaohezi",  "name": "📺 小盒子4K", "type": 1, "api": "http://xhztv.top/4k.json",                        "searchable": 1, "quickSearch": 1},
            {"key": "jianpian",  "name": "🎬 荐片",     "type": 1, "api": "https://tv.203511.xyz/0821.json",                 "searchable": 1, "quickSearch": 1},
            {"key": "fmys",      "name": "🐴 fmys",     "type": 1, "api": "http://fmys.top/fmys.json",                       "searchable": 1, "quickSearch": 1},
            {"key": "jundie",    "name": "👨 俊哥",     "type": 1, "api": "http://home.jundie.top:81/top98.json",            "searchable": 1, "quickSearch": 1},
            {"key": "xiaopingguo","name":"🍎 小蘋果",   "type": 1, "api": "https://bitbucket.org/xduo/duoapi/raw/master/xpg.json", "searchable": 1, "quickSearch": 1},
        ],
        "flags": ["4K", "1080P", "720P", "優酷", "愛奇藝", "騰訊", "芒果"],
        "update_time": now_display(),
    }

    config_path = OUTPUT_DIR / "config.json"
    save_json(config, config_path, False)
    return config_path
