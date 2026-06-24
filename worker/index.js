/**
 * Chill-AI-TV — Cloudflare Worker (智能聚合版)
 * 自動從配置源發現可用 API，快取後聚合搜尋
 */
// 快取：每小時刷新一次可用 API 列表
let apiCache = null;
let cacheTime = 0;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === '/health') return new Response('OK', { status: 200 });

    // 所有請求 → config.json
    if (path === '/' || path === '/api') return serveConfig();

    // 搜尋 + 瀏覽 → 聚合
    return handleRequest(url);
  },
};

// ========== Config 伺服 ==========
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

// ========== 聚合請求處理 ==========
async function handleRequest(url) {
  const wd = url.searchParams.get('wd') || '';

  // 1. 獲取可用的直接 API 列表（快取）
  const apis = await getAvailableAPIs();

  // 2. 有搜尋關鍵字 → 聚合搜尋
  if (wd) {
    const results = await Promise.all(apis.map(api => searchOne(api.name, api.url, wd)));
    const all = [];
    const seen = new Set();
    for (const r of results) {
      for (const item of r.items) {
        const k = (item.vod_name || '').replace(/\s+/g, '').toLowerCase().slice(0, 20);
        if (!seen.has(k) && k) { seen.add(k); all.push(item); }
      }
    }
    const hitSources = results.filter(r => r.items.length > 0).map(r => r.name);
    return json({
      code: 1, msg: `「${wd}」- ${all.length}結果 (${hitSources.join('+')})`,
      page: 1, pagecount: Math.max(1, Math.ceil(all.length / 20)),
      limit: 20, total: all.length, list: all.slice(0, 100), class: [],
    });
  }

  // 3. 無關鍵字 → 瀏覽（用第一個可用 API 的分類）
  if (apis.length > 0) {
    try {
      const r = await fetch(apis[0].url, {
        headers: { 'User-Agent': 'ChillAITV/1.0' },
        signal: AbortSignal.timeout(8000),
      });
      if (r.ok) {
        const data = await r.json();
        // 過濾成人分類
        const blocked = [29, 73];
        if (data.list) data.list = data.list.filter(it => !blocked.includes(it.type_id));
        if (data.class) data.class = data.class.filter(it => !blocked.includes(it.type_id));
        return json(data);
      }
    } catch {}
  }
  return json({ code: 1, msg: 'Chill-AI-TV', list: [], class: [] });
}

// ========== 智能發現可用 API ==========
async function getAvailableAPIs() {
  const now = Date.now();
  if (apiCache && (now - cacheTime) < 3600000) return apiCache; // 快取 1 小時

  // 配置源列表（CDN/全球可達）
  const configSources = [
    'https://qist.wyfc.qzz.io/fty.json',
    'https://qist.wyfc.qzz.io/xiaosa/api.json',
    'https://cdn.jsdelivr.net/gh/liu673cn/box@main/m.json',
    'https://tv.203511.xyz/0821.json',
    'https://6800.kstore.vip/fish.json',
    'https://bitbucket.org/xduo/duoapi/raw/master/xpg.json',
  ];

  // 已知可用的直接 API
  const directAPIs = [
    { name: '暴風', url: 'https://bfzyapi.com/api.php/provide/vod' },
  ];

  // 從配置源提取直接 API
  const discovered = [];
  for (const src of configSources) {
    try {
      const r = await fetch(src, {
        headers: { 'User-Agent': 'ChillAITV/1.0' },
        signal: AbortSignal.timeout(5000),
      });
      if (r.ok) {
        const data = await r.json();
        const sites = data.sites || [];
        for (const site of sites) {
          const api = site.api || site.ext || '';
          if (api.includes('api.php/provide/vod') && api.startsWith('http')) {
            const name = site.name || site.key || api.split('/')[2];
            discovered.push({ name: name.substring(0, 12), url: api });
          }
        }
      }
    } catch {}
  }

  // 合併去重
  const seen = new Set(['https://bfzyapi.com/api.php/provide/vod']);
  const result = [...directAPIs];
  for (const d of discovered) {
    if (!seen.has(d.url)) {
      seen.add(d.url);
      result.push(d);
    }
  }

  apiCache = result;
  cacheTime = now;
  return result;
}

// ========== 搜尋單個 API ==========
async function searchOne(name, api, wd) {
  try {
    const r = await fetch(`${api}?ac=detail&wd=${encodeURIComponent(wd)}`, {
      headers: { 'User-Agent': 'ChillAITV/1.0' },
      signal: AbortSignal.timeout(5000),
    });
    if (!r.ok) return { name, items: [] };
    const data = await r.json();
    const items = (data.list || []).map(it => ({
      ...it, _source: name, vod_remarks: name + '·' + (it.vod_remarks || ''),
    }));
    return { name, items };
  } catch { return { name, items: [] }; }
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' },
  });
}
