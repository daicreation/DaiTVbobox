/**
 * Chill-AI-TV — Cloudflare Worker (聚合搜尋版)
 * 一個網址搞定：搜尋自動合併暴風+索尼+海外看+非凡等多個源
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    const GITHUB_API = 'https://api.github.com/repos/daicreation/DaiTVbobox/contents';

    // ---- 聚合搜尋 API ----
    if (path === '/search') {
      return handleAggregatedSearch(request);
    }

    // ---- 聚合首頁內容 ----
    if (path === '/home') {
      return handleAggregatedHome(request);
    }

    // ---- 健康檢查 ----
    if (path === '/health') {
      return new Response('OK', { status: 200, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }

    // ---- 靜態 JSON（從 GitHub API 讀取）----
    const routes = {
      '/':         '/output/config.json',
      '/api':      '/output/config.json',
      '/movie':    '/output/movie.json',
      '/tv':       '/output/tv.json',
      '/variety':  '/output/variety.json',
      '/live':     '/output/live.json',
    };

    const filePath = routes[path];
    if (!filePath) {
      return json({ error: 'Not Found' }, 404);
    }

    try {
      const resp = await fetch(GITHUB_API + filePath, {
        headers: { 'User-Agent': 'ChillAITV/1.0', 'Accept': 'application/vnd.github.v3+json' },
      });
      if (!resp.ok) return json({ error: 'Upstream' }, 502);
      const data = await resp.json();
      const binary = atob(data.content.replace(/\s/g, ''));
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const content = new TextDecoder('utf-8').decode(bytes);
      return new Response(content, {
        status: 200,
        headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=1800' },
      });
    } catch (err) {
      return json({ error: err.message }, 503);
    }
  },
};

// ============================================================
// 聚合搜尋：同時查詢多個優質源，合併去重
// ============================================================
async function handleAggregatedSearch(request) {
  const url = new URL(request.url);
  const keyword = url.searchParams.get('wd') || '';
  if (!keyword) return json({ code: 0, msg: '請輸入關鍵字', list: [] });

  // 精選優質源（支援搜尋 + 海外可連）
  const sources = [
    { name: '暴風',   api: 'https://bfzyapi.com/api.php/provide/vod' },
    { name: '索尼',   api: 'https://suoniapi.com/api.php/provide/vod' },
    { name: '海外看', api: 'https://haiwaikan.com/api.php/provide/vod' },
    { name: '非凡',   api: 'http://cj.ffzyapi.com/api.php/provide/vod' },
  ];

  // 並行搜尋所有源
  const promises = sources.map(async (src) => {
    try {
      const apiUrl = `${src.api}?ac=detail&wd=${encodeURIComponent(keyword)}`;
      const resp = await fetch(apiUrl, {
        headers: { 'User-Agent': 'ChillAITV/1.0', 'Accept': 'application/json' },
        signal: AbortSignal.timeout(8000),
      });
      if (!resp.ok) return { name: src.name, list: [] };
      const data = await resp.json();
      const items = (data.list || []).map(it => ({ ...it, _source: src.name }));
      return { name: src.name, list: items };
    } catch {
      return { name: src.name, list: [] };
    }
  });

  const results = await Promise.all(promises);
  const allItems = results.flatMap(r => r.list);

  // 去重（按 vod_name + vod_year 相似度）
  const seen = new Set();
  const merged = [];
  for (const item of allItems) {
    const key = (item.vod_name || '').replace(/\s+/g, '').toLowerCase().substring(0, 20);
    if (!seen.has(key)) {
      seen.add(key);
      // vod_remarks 標記來源
      item.vod_remarks = item._source + '·' + (item.vod_remarks || '');
      merged.push(item);
    }
  }

  return json({
    code: 1,
    msg: `聚合搜尋：${keyword}`,
    page: 1,
    pagecount: Math.ceil(merged.length / 20),
    limit: 20,
    total: merged.length,
    list: merged.slice(0, 100),
    sources: results.filter(r => r.list.length > 0).map(r => r.name),
  });
}

// ============================================================
// 聚合首頁：合併多源熱門內容
// ============================================================
async function handleAggregatedHome(request) {
  const sources = [
    { name: '暴風',   api: 'https://bfzyapi.com/api.php/provide/vod', tid: 20 },  // 電影
  ];

  const allItems = [];
  for (const src of sources) {
    try {
      const apiUrl = `${src.api}?ac=detail&t=${src.tid}&pg=1`;
      const resp = await fetch(apiUrl, {
        headers: { 'User-Agent': 'ChillAITV/1.0', 'Accept': 'application/json' },
        signal: AbortSignal.timeout(8000),
      });
      if (resp.ok) {
        const data = await resp.json();
        const items = (data.list || []).map(it => ({ ...it, _source: src.name }));
        allItems.push(...items);
      }
    } catch {}
  }

  const seen = new Set();
  const merged = allItems.filter(item => {
    const key = (item.vod_name || '').replace(/\s+/g, '').toLowerCase().substring(0, 20);
    if (seen.has(key)) return false;
    seen.add(key);
    item.vod_remarks = item._source + '·' + (item.vod_remarks || '');
    return true;
  });

  return json({
    code: 1,
    msg: 'Chill-AI-TV 首頁',
    page: 1,
    pagecount: Math.ceil(merged.length / 20),
    limit: 20,
    total: merged.length,
    list: merged.slice(0, 100),
    class: [
      { type_name: '全部', type_id: '0' },
      { type_name: '動作', type_id: '21' },
      { type_name: '喜劇', type_id: '22' },
      { type_name: '恐怖', type_id: '23' },
      { type_name: '科幻', type_id: '24' },
      { type_name: '愛情', type_id: '25' },
      { type_name: '劇情', type_id: '26' },
    ],
  });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' },
  });
}
