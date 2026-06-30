# Hot TV KV Plan

## Goal

Stabilize `Chill-TV` homepage data by serving `output/hot_tv.json` from Cloudflare KV first, with GitHub as fallback.

## Scope

- Update `worker/index.js` to read `hot_tv.json` from KV before GitHub.
- Keep existing GitHub fallback so rollout is safe.
- Update GitHub Actions to upload `output/hot_tv.json` into KV after build/publish.
- Add tests for KV-first behavior and fallback behavior.

## Notes

- Only `hot_tv.json` moves to KV in this phase.
- `config.json` remains on the existing GitHub-backed path for now.
- Required GitHub secrets for KV sync:
  - `CF_API_TOKEN`
  - `CF_ACCOUNT_ID`
  - `CF_KV_NAMESPACE_ID`
