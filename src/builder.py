"""Chill-AI-TV — Builder (config 由 Worker 動態生成)"""
from .constants import OUTPUT_DIR
from .utils import save_json, now_display

def build_all_outputs(all_items=None, rules_config=None, domain=""):
    """生成輸出 JSON"""
    save_json({"update_time": now_display()}, OUTPUT_DIR / "summary.json")
    return {"summary": OUTPUT_DIR / "summary.json"}
