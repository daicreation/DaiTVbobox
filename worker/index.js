/**
 * Chill-AI-TV — Worker (聚合引擎)
 * /api.php/provide/vod → 瀏覽=暴風, 搜尋=聚合多源
 */
// 請求記錄（debug）
let lastRequests = [];

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const wd = url.searchParams.get('wd') || '';

    // 請求記錄（debug）
    if (path === '/health') return new Response('OK', { status: 200 });
    if (path === '/log') return new Response(JSON.stringify(lastRequests, null, 2), {
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    });

    // 首頁 config
    if (path === '/' || path === '/api') {
      return new Response(JSON.stringify({
        sites: [{
          key: "Chill_AI_TV",
          name: "🧊 Chill-AI-TV",
          type: 1,
          api: "https://daitvbobox.chungshare.workers.dev/api.php/provide/vod",
          searchable: 1, quickSearch: 1, filterable: 1,
        }],
        flags: ["4K", "1080P", "720P", "優酷", "愛奇藝", "騰訊", "芒果"],
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-cache' },
      });
    }

    // API 端點
    if (path === '/api.php/provide/vod') {
      // 記錄非搜尋/瀏覽請求（debug）
      const ac = url.searchParams.get('ac') || '';
      if (!wd && ac && ac !== 'detail') {
        lastRequests.unshift({ time: new Date().toISOString(), params: Object.fromEntries(url.searchParams) });
        if (lastRequests.length > 10) lastRequests = lastRequests.slice(0, 10);
      }
      if (wd) return handleSearch(wd);
      if (!ac || ac === 'detail') return proxyBrowse();
      return proxyAny(url.search);
    }

    return json({ error: 'Not Found' }, 404);
  },
};

// ========== 瀏覽：代理暴風（快速）==========
async function proxyBrowse() {
  try {
    const r = await fetch('https://bfzyapi.com/api.php/provide/vod', {
      headers: { 'User-Agent': 'ChillAITV/1.0' },
      signal: AbortSignal.timeout(8000),
    });
    const data = await r.json();
    const blocked = [29, 73];
    if (data.list) data.list = data.list.filter(it => !blocked.includes(it.type_id));
    if (data.class) data.class = data.class.filter(it => !blocked.includes(it.type_id));
    return json(data);
  } catch { return json({ code: 0, list: [], class: [] }); }
}

// ========== 聚合搜尋 ==========
async function handleSearch(wd) {
  const sources = [
    { key: "bfzy", name: "🔥 暴風", api: "https://bfzyapi.com/api.php/provide/vod" },
    { key: "ff",   name: "⚡ 非凡", api: "http://cj.ffzyapi.com/api.php/provide/vod" },
    { key: "sn",   name: "🎯 索尼", api: "https://suoniapi.com/api.php/provide/vod" },
    { key: "lz",   name: "🔮 量子", api: "https://cj.lziapi.com/api.php/provide/vod/" },
    { key: "360",  name: "💠 360",  api: "https://360zyzz.com/api.php/provide/vod/" },
    { key: "js",   name: "⚡ 極速", api: "https://jszyapi.com/api.php/provide/vod/" },
    { key: "jy",   name: "🦅 金鷹", api: "https://jyzyapi.com/provide/vod/" },
  ];

  const results = await Promise.all(sources.map(async (src) => {
    try {
      const r = await fetch(`${src.api}?ac=detail&wd=${encodeURIComponent(wd)}`, {
        headers: { 'User-Agent': 'ChillAITV/1.0' },
        signal: AbortSignal.timeout(6000),
      });
      if (!r.ok) return [];
      const d = await r.json();
      return (d.list || []).map(it => ({
        ...it,
        _source: src.name,
        vod_remarks: src.name + "·" + (it.vod_remarks || ''),
      }));
    } catch { return []; }
  }));

  const all = results.flat();
  const seen = new Set();
  const list = all.filter(it => {
    const k = (it.vod_name || '').replace(/\s+/g, '').toLowerCase().slice(0, 20);
    if (seen.has(k) || !k) return false;
    seen.add(k);
    return true;
  });

  return json({
    code: 1, msg: "Chill-AI-TV",
    page: 1, pagecount: Math.max(1, Math.ceil(list.length / 20)),
    limit: 20, total: list.length, list: list.slice(0, 100), class: [],
  });
}

// 來源 key → API URL 對照（與 handleSearch 的 sources 一致）
const SRC_MAP = {
  "bfzy": "https://bfzyapi.com/api.php/provide/vod",
  "ff":    "http://cj.ffzyapi.com/api.php/provide/vod",
  "sn":    "https://suoniapi.com/api.php/provide/vod",
  "lz":    "https://cj.lziapi.com/api.php/provide/vod/",
  "360":   "https://360zyzz.com/api.php/provide/vod/",
  "js":    "https://jszyapi.com/api.php/provide/vod/",
  "jy":    "https://jyzyapi.com/provide/vod/",
};

// ========== 通用代理（詳情請求，根據 vod_id 路由到正確 API）==========
async function proxyAny(search) {
  const url = new URL("https://localhost" + search);
  const ids = url.searchParams.get('ids') || '';

  // 從 vod_id 解析來源（格式: src_key_realid）
  for (const [key, api] of Object.entries(SRC_MAP)) {
    if (ids.startsWith(key + "_")) {
      // 去除前綴，用正確的 API
      const realIds = ids.replace(key + "_", "");
      const newSearch = search.replace(ids, realIds);
      try {
        const r = await fetch(api + newSearch, {
          headers: { 'User-Agent': 'ChillAITV/1.0' },
          signal: AbortSignal.timeout(5000),
        });
        if (r.ok) {
          const text = await r.text();
          if (text.length > 50) return new Response(text, {
            headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=300' },
          });
        }
      } catch {}
      break;
    }
  }
  // 備用：嘗試所有 API
  for (const api of Object.values(SRC_MAP)) {
    try {
      const r = await fetch(api + search, {
        headers: { 'User-Agent': 'ChillAITV/1.0' },
        signal: AbortSignal.timeout(5000),
      });
      if (r.ok) {
        const text = await r.text();
        if (text.length > 50) return new Response(text, {
          headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=300' },
        });
      }
    } catch {}
  }
  return json({ code: 0, msg: "無數據", list: [] });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=300' },
  });
}
