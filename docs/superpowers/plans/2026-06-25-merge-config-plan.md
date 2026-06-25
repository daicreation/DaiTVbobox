# Merge Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/`, `/hk`, and `/cn` serve the same TVBox configuration again.

**Architecture:** Keep the content-only source cleanup, but remove region-specific config ordering and route-specific config loading. Root and regional aliases will all resolve to the same config and the same `/api` and `/p/*` proxy paths.

**Tech Stack:** Python builder, Cloudflare Worker, pytest, Node syntax check

---

### Task 1: Align builder output to one shared config

**Files:**
- Modify: `src/builder.py`
- Modify: `tests/test_builder.py`

- [ ] Update builder core site generation so all config outputs use root `/api` and `/p/*` paths.
- [ ] Keep `config.json`, `config.hk.json`, and `config.cn.json` as identical aliases for compatibility.
- [ ] Update tests to expect identical HK/CN/root config ordering and root proxy paths.

### Task 2: Align worker routing to one shared config

**Files:**
- Modify: `worker/index.js`

- [ ] Make `/`, `/hk`, and `/cn` all load `output/config.json`.
- [ ] Keep `/hk/api`, `/cn/api`, `/hk/p/*`, and `/cn/p/*` working as aliases so existing installs do not break.
- [ ] Preserve adult-category filtering in proxy responses.

### Task 3: Verify and publish

**Files:**
- Modify: `output/config.json`
- Modify: `output/config.hk.json`
- Modify: `output/config.cn.json`

- [ ] Run targeted pytest for builder behavior.
- [ ] Run `node --check worker/index.js`.
- [ ] Rebuild config outputs if needed, commit, push, and verify live `/`, `/hk`, and `/cn` match.
