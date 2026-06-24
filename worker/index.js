/**
 * Chill-AI-TV — Cloudflare Worker
 * 瀏覽 → 暴風代理（快速）
 * 搜尋 → 暴風優先 + 海外看/非凡做補充
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const wd = url.searchParams.get('wd') || '';

    // 健康檢查
    if (path === '/health') return new Response('OK', { status: 200 });

    // 靜態 config.json
    if (path === '/' || path === '/api') return serveConfig();

    // 搜尋模式 → 聚合多源
    if (wd) return handleSearch(wd);

    // 瀏覽模式 → 純代理暴風（快速穩定）
    return proxyToBfzy(url.search);
  },
};

// ========== Config ==========
async function serveConfig() {
  try {
    const resp = await fetch('https://api.github.com/repos/daicreation/DaiTVbobox/contents/output/config.json', {
      headers: { 'User-Agent': 'ChillAITV/1.0', 'Accept': 'application/vnd.github.v3+json' },
    });
    const data = await resp.json();
    const binary = atob(data.content.replace(/\s/g, ''));
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return new Response(new TextDecoder('utf-8').decode(bytes), {
      status: 200,
      headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=1800' },
    });
  } catch (e) {
    return json({ error: e.message }, 503);
  }
}

// ========== 代理暴風（過濾成人分類）==========
// 要過濾的 type_id：29(理论片), 73(福利)
const BLOCKED_IDS = [29, 73];
const BLOCKED_NAMES = ['理论片', '福利'];

async function proxyToBfzy(search) {
  try {
    const r = await fetch('https://bfzyapi.com/api.php/provide/vod' + search, {
      headers: { 'User-Agent': 'ChillAITV/1.0' },
      signal: AbortSignal.timeout(10000),
    });
    const text = await r.text();
    const data = JSON.parse(text);
    // 過濾 list 和 class
    if (data.list) data.list = data.list.filter(it => !BLOCKED_IDS.includes(it.type_id) && !BLOCKED_NAMES.includes(it.type_name));
    if (data.class) data.class = data.class.filter(it => !BLOCKED_IDS.includes(it.type_id) && !BLOCKED_NAMES.includes(it.type_name));
    return json(data);
  } catch (e) {
    return json({ error: e.message }, 503);
  }
}

// ========== 聚合搜尋 ==========
async function handleSearch(wd) {
  // 主要源：暴風（必定查）
  const primary = await searchSource('暴風', 'https://bfzyapi.com/api.php/provide/vod', wd);

  // 補充源：海外看 + 非凡 + 索尼（並行查，不阻塞主結果）
  const secondary = await Promise.all([
    searchSource('海外看', 'https://haiwaikan.com/api.php/provide/vod', wd),
    searchSource('非凡',   'http://cj.ffzyapi.com/api.php/provide/vod', wd),
    searchSource('索尼',   'https://suoniapi.com/api.php/provide/vod', wd),
  ]);

  // 合併結果（暴風優先 + 補充源去重）
  const all = [...primary];
  const seen = new Set(all.map(it => (it.vod_name || '').replace(/\s+/g, '').toLowerCase().slice(0, 20)));

  for (const srcItems of secondary) {
    for (const it of srcItems) {
      const k = (it.vod_name || '').replace(/\s+/g, '').toLowerCase().slice(0, 20);
      if (!seen.has(k) && k) {
        seen.add(k);
        all.push(it);
      }
    }
  }

  const sourcesHit = [primary.length > 0 ? '暴風' : null, ...secondary.map((s, i) => s.length > 0 ? ['海外看', '非凡', '索尼'][i] : null)].filter(Boolean);

  // 過濾成人內容
  const filtered = all.filter(it => !BLOCKED_IDS.includes(it.type_id) && !BLOCKED_NAMES.includes(it.type_name));

  return json({
    code: 1,
    msg: `「${wd}」- ${filtered.length} 結果 (${sourcesHit.join('+')})`,
    page: 1,
    pagecount: Math.max(1, Math.ceil(filtered.length / 20)),
    limit: 20,
    total: filtered.length,
    list: filtered.slice(0, 100),
    class: [],
  });
}

async function searchSource(name, api, wd) {
  try {
    const formats = [`?ac=detail&wd=${encodeURIComponent(wd)}`, `?ac=videolist&wd=${encodeURIComponent(wd)}`, `?wd=${encodeURIComponent(wd)}`];
    for (const fmt of formats) {
      const r = await fetch(api + fmt, {
        headers: { 'User-Agent': 'ChillAITV/1.0' },
        signal: AbortSignal.timeout(5000),
      });
      if (r.ok) {
        const d = await r.json();
        if ((d.list || []).length > 0) {
          return d.list.map(it => ({ ...it, _source: name, vod_remarks: name + '·' + (it.vod_remarks || '') }));
        }
      }
    }
    return [];
  } catch { return []; }
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' },
  });
}
