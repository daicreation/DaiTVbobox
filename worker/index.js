/**
 * Chill-AI-TV — Cloudflare Worker (聚合搜尋版 v2)
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const GITHUB_API = 'https://api.github.com/repos/daicreation/DaiTVbobox/contents';

    // ---- 聚合搜尋 ----
    if (path === '/search') return handleAggregatedSearch(request);

    // ---- 健康檢查 ----
    if (path === '/health') return new Response('OK', { status: 200 });

    // ---- 靜態 JSON ----
    const routes = {
      '/':         '/output/config.json',
      '/api':      '/output/config.json',
      '/movie':    '/output/movie.json',
      '/tv':       '/output/tv.json',
      '/variety':  '/output/variety.json',
      '/live':     '/output/live.json',
    };
    const fp = routes[path];
    if (!fp) return json({ error: 'Not Found' }, 404);

    try {
      const resp = await fetch(GITHUB_API + fp, {
        headers: { 'User-Agent': 'ChillAITV/1.0', 'Accept': 'application/vnd.github.v3+json' },
      });
      if (!resp.ok) return json({ error: 'Upstream' }, 502);
      const data = await resp.json();
      const binary = atob(data.content.replace(/\s/g, ''));
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      return new Response(new TextDecoder('utf-8').decode(bytes), {
        status: 200,
        headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=1800' },
      });
    } catch (err) {
      return json({ error: err.message }, 503);
    }
  },
};

// ============================================================
// 聚合搜尋
// ============================================================
async function handleAggregatedSearch(request) {
  const url = new URL(request.url);
  const wd = url.searchParams.get('wd') || '';
  if (!wd) return json({ code: 1, msg: 'Chill-AI-TV', list: [] });

  const sources = [
    { name: '暴風',   api: 'https://bfzyapi.com/api.php/provide/vod' },
    { name: '海外看', api: 'https://haiwaikan.com/api.php/provide/vod' },
    { name: '非凡',   api: 'http://cj.ffzyapi.com/api.php/provide/vod' },
  ];

  const promises = sources.map(async (src) => {
    try {
      const u = `${src.api}?ac=detail&wd=${encodeURIComponent(wd)}`;
      const r = await fetch(u, {
        headers: { 'User-Agent': 'ChillAITV/1.0' },
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) return [];
      const data = await r.json();
      return (data.list || []).map(it => ({ ...it, _source: src.name }));
    } catch {
      return [];
    }
  });

  const all = (await Promise.all(promises)).flat();
  const seen = new Set();
  const merged = all.filter(it => {
    const k = (it.vod_name || '').replace(/\s+/g, '').toLowerCase().slice(0, 20);
    if (seen.has(k) || !k) return false;
    seen.add(k);
    it.vod_remarks = it._source + '·' + (it.vod_remarks || '');
    return true;
  });

  return json({
    code: 1,
    msg: `「${wd}」- ${merged.length} 結果`,
    page: 1,
    pagecount: Math.max(1, Math.ceil(merged.length / 20)),
    limit: 20,
    total: merged.length,
    list: merged.slice(0, 100),
  });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' },
  });
}
