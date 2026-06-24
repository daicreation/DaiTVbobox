# ============================================================
# TVBox 影視聚合系統 — 模組⑤: 發布提交 (publisher)
#
# 功能：
#   1. 將生成的 JSON 寫入 output/ 目錄
#   2. 執行 git add / git commit / git push
#   3. 可選：呼叫 Cloudflare API 清除 Worker 快取
#   4. 生成執行摘要 (summary.json)
#
# 注意：
#   - GitHub Actions 環境中 GITHUB_TOKEN 自動可用
#   - 本機測試時需要手動設定 Git 遠端
# ============================================================

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .constants import (
    ROOT_DIR,
    OUTPUT_DIR,
    LOGS_DIR,
    RULES_YAML_PATH,
)
from .utils import (
    logger,
    load_yaml,
    save_json,
    now_display,
    now_iso,
)


def publish(
    output_paths: dict[str, Path],
    summary: Optional[dict] = None,
    rules_config: Optional[dict] = None,
) -> bool:
    """
    發布所有輸出到 GitHub Repo

    這是模組的主入口函數

    步驟：
    1. 驗證所有輸出檔案存在
    2. 寫入執行摘要
    3. git add output/
    4. git commit (帶時間戳)
    5. git push
    6. 可選：清除 Cloudflare 快取

    Args:
        output_paths: builder 的輸出 {"movie": Path, "tv": Path, ...}
        summary: 執行摘要 dict
        rules_config: 評分規則

    Returns:
        發布成功返回 True
    """
    if rules_config is None:
        rules_config = load_yaml(RULES_YAML_PATH)

    # ---- 步驟 1: 驗證輸出 ----
    logger.info("=" * 60)
    logger.info("開始發布流程")
    logger.info("=" * 60)

    for category, path in output_paths.items():
        if not path.exists():
            logger.error(f"輸出檔案不存在: {path}")
            return False
        file_size = path.stat().st_size
        logger.info(f"  ✓ {category}: {path.name} ({file_size:,} bytes)")

    # ---- 步驟 2: 寫入執行摘要 ----
    if summary is None:
        summary = _build_summary(output_paths)

    summary_path = OUTPUT_DIR / "summary.json"
    save_json(summary, summary_path)
    logger.info(f"  執行摘要: {summary_path.name}")

    # ---- 步驟 3: Git 操作 ----
    # 檢查是否在 Git Repo 中
    if not (ROOT_DIR / ".git").exists():
        logger.warning("不在 Git Repo 中，跳過 git push")
        logger.info(f"輸出檔案已生成在: {OUTPUT_DIR}")
        return True

    try:
        # 設定 Git 使用者資訊 (GitHub Actions 環境)
        _setup_git_config()

        # git add
        _run_git(["add", "output/"])
        logger.info("  git add output/ ✓")

        # 檢查是否有變更
        status = _run_git(["status", "--porcelain", "output/"])
        if not status.strip():
            logger.info("  沒有變更，跳過 commit")
            return True

        # git commit
        commit_msg = _build_commit_message(summary)
        _run_git(["commit", "-m", commit_msg])
        logger.info(f"  git commit ✓: {commit_msg}")

        # git push
        _run_git(["push"])
        logger.info("  git push ✓")

        logger.info("=" * 60)
        logger.info("發布完成！")
        logger.info("=" * 60)
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Git 操作失敗: {e}")
        logger.error(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"發布過程異常: {e}")
        return False


def _setup_git_config() -> None:
    """
    設定 Git 使用者資訊

    在 GitHub Actions 中使用 Actions Bot 身分
    本機環境使用已設定的 Git 使用者
    """
    # GitHub Actions 環境變數
    is_actions = os.environ.get("GITHUB_ACTIONS") == "true"

    if is_actions:
        # 使用 GitHub Actions Bot
        _run_git(["config", "user.name", "github-actions[bot]"])
        _run_git(["config", "user.email", "github-actions[bot]@users.noreply.github.com"])
        logger.debug("Git 設定: github-actions[bot]")

        # 設定遠端 URL (使用 PAT 認證)
        token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN", "")
        if token:
            repo = os.environ.get("GITHUB_REPOSITORY", "")
            if repo:
                remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"
                _run_git(["remote", "set-url", "origin", remote_url])
                logger.debug("Git 遠端已設定 (使用 PAT 認證)")


def _build_commit_message(summary: dict) -> str:
    """
    建立 Git commit 訊息

    包含執行時間和各類別統計

    Args:
        summary: 執行摘要

    Returns:
        Commit 訊息字串
    """
    lines = [
        f"🤖 [Bot] 每日自動更新 — {summary.get('build_time', 'unknown')}",
        "",
    ]
    for category, stats in summary.get("categories", {}).items():
        lines.append(
            f"  {category}: {stats.get('total', 0)} 個影片, "
            f"{stats.get('sources', 0)} 個可用來源"
        )

    lines.append("")
    lines.append(f"  總來源數: {summary.get('total_sources', 0)}")
    lines.append(f"  可用率: {summary.get('availability_rate', 'N/A')}")

    return "\n".join(lines)


def _build_summary(output_paths: dict[str, Path]) -> dict:
    """
    建立執行摘要

    從各 output JSON 讀取統計資訊

    Args:
        output_paths: 輸出檔案路徑

    Returns:
        摘要 dict
    """
    categories = {}
    total_sources = 0
    total_items = 0

    for category, path in output_paths.items():
        if category == "config" or not path.exists():
            continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            items = data.get("list", [])
            item_count = len(items)
            source_count = sum(
                item.get("source_count", 0)
                for item in items
            )

            categories[category] = {
                "total": item_count,
                "sources": source_count,
            }
            total_items += item_count
            total_sources += source_count

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"讀取 {path.name} 失敗: {e}")
            categories[category] = {"total": 0, "sources": 0}

    # 計算可用率
    # (此處為簡化計算，實際可用率應從 health_checker 結果計算)
    availability_rate = "N/A"

    return {
        "build_time": now_display(),
        "build_iso": now_iso(),
        "total_items": total_items,
        "total_sources": total_sources,
        "availability_rate": availability_rate,
        "categories": categories,
        "builder_version": "1.0.0",
    }


def _run_git(args: list[str]) -> str:
    """
    執行 Git 命令

    Args:
        args: Git 命令參數列表

    Returns:
        stdout 輸出

    Raises:
        subprocess.CalledProcessError: Git 命令失敗
    """
    cmd = ["git"] + args
    logger.debug(f"執行: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,  # 最長等待 2 分鐘
    )

    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd,
            output=result.stdout,
            stderr=result.stderr,
        )

    return result.stdout.strip()


# 可選：清除 Cloudflare 快取
def purge_cloudflare_cache(
    zone_id: Optional[str] = None,
    api_token: Optional[str] = None,
    urls: Optional[list[str]] = None,
) -> bool:
    """
    清除 Cloudflare CDN 快取

    在發布新 JSON 後調用，確保 Worker 回傳最新內容

    Args:
        zone_id: Cloudflare Zone ID
        api_token: Cloudflare API Token
        urls: 要清除快取的 URL 列表

    Returns:
        成功返回 True
    """
    zone_id = zone_id or os.environ.get("CF_ZONE_ID", "")
    api_token = api_token or os.environ.get("CF_API_TOKEN", "")

    if not zone_id or not api_token:
        logger.info("未設定 Cloudflare 憑證，跳過快取清除")
        return False

    if not urls:
        # 預設清除所有 output 相關 URL
        domain = os.environ.get("WORKER_DOMAIN", "https://tv.xxx.com")
        urls = [
            f"{domain}/",
            f"{domain}/movie",
            f"{domain}/tv",
            f"{domain}/variety",
            f"{domain}/live",
            f"{domain}/config.json",
        ]

    import httpx
    api_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache"

    try:
        client = httpx.Client(timeout=30)
        response = client.post(
            api_url,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json={"files": urls},
        )
        response.raise_for_status()
        result = response.json()
        if result.get("success"):
            logger.info(f"Cloudflare 快取已清除: {len(urls)} 個 URL")
            return True
        else:
            logger.error(f"Cloudflare 清除失敗: {result}")
            return False
    except Exception as e:
        logger.error(f"Cloudflare API 異常: {e}")
        return False


# ---- 命令列入口 ----
if __name__ == "__main__":
    from .utils import setup_logging
    setup_logging("INFO")
    print("=" * 60)
    print("TVBox 發布模組 — 測試模式")
    print("=" * 60)
    # 檢查 output/ 目錄
    json_files = list(OUTPUT_DIR.glob("*.json"))
    if json_files:
        paths = {f.stem: f for f in json_files}
        success = publish(paths)
        print(f"發布結果: {'成功' if success else '失敗'}")
    else:
        print(f"output/ 目錄為空，請先執行 builder")
