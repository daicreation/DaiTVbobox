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
            {"key": "Chill_AI_TV", "name": "🧊 Chill-AI-TV", "type": 1, "api": f"{domain}/api.php/provide/vod", "searchable": 1, "quickSearch": 1, "filterable": 1},
        ],
        "flags": ["4K", "1080P", "720P", "優酷", "愛奇藝", "騰訊", "芒果"],
        "update_time": now_display(),
    }

    config_path = OUTPUT_DIR / "config.json"
    save_json(config, config_path, False)
    return config_path
