/**
 * Chill-AI-TV — Cloudflare Worker v3
 * 請求記錄 + 聚合搜尋 + 分類
 */
// 記錄最近 20 筆請求（用來 debug TVBox）
let requestLog = [];

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const GITHUB_API = 'https://api.github.com/repos/daicreation/DaiTVbobox/contents';

    // 記錄請求（保留最近 20 筆）
    requestLog.unshift({
      time: new Date().toISOString(),
      path: path,
      method: request.method,
      params: Object.fromEntries(url.searchParams),
      ua: (request.headers.get('User-Agent') || '').substring(0, 80),
    });
    if (requestLog.length > 20) requestLog = requestLog.slice(0, 20);

    // ---- 查看 TVBox 請求記錄 ----
    if (path === '/log') {
      return new Response(JSON.stringify(requestLog, null, 2), {
        status: 200,
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
      });
    }

    // ---- 聚合搜尋 + 瀏覽 ----
    if (path === '/search') return handleSearch(request);

    // ---- 健康檢查 ----
    if (path === '/health') return new Response('OK', { status: 200 });

    // ---- 靜態 JSON ----
    const routes = {
      '/':         '/output/config.json',
      '/api':      '/output/config.json',
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

async function handleSearch(request) {
  const url = new URL(request.url);
  const wd = url.searchParams.get('wd') || url.searchParams.get('keyword') || url.searchParams.get('q') || '';

  // ---- 有搜尋關鍵字 → 聚合暴風+海外看+非凡 ----
  if (wd && wd.length >= 1) {
    const sources = [
      { name: '暴風',   api: 'https://bfzyapi.com/api.php/provide/vod' },
      { name: '非凡',   api: 'http://cj.ffzyapi.com/api.php/provide/vod' },
      { name: '海外看', api: 'https://haiwaikan.com/api.php/provide/vod' },
    ];
    const results = await Promise.all(sources.map(async (src) => {
      try {
        const r = await fetch(`${src.api}?ac=detail&wd=${encodeURIComponent(wd)}`, {
          headers: { 'User-Agent': 'ChillAITV/1.0' },
          signal: AbortSignal.timeout(6000),
        });
        if (!r.ok) return [];
        const d = await r.json();
        return (d.list || []).map(it => ({ ...it, _source: src.name, vod_remarks: src.name + '·' + (it.vod_remarks || '') }));
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
      code: 1, msg: `「${wd}」- ${list.length} 結果`,
      page: 1, pagecount: Math.max(1, Math.ceil(list.length / 20)),
      limit: 20, total: list.length, list: list.slice(0, 100),
      class: [],
    });
  }

  // ---- 無關鍵字 → 回傳暴風首頁（含全部分類）----
  try {
    const r = await fetch('https://bfzyapi.com/api.php/provide/vod', {
      headers: { 'User-Agent': 'ChillAITV/1.0' },
      signal: AbortSignal.timeout(6000),
    });
    if (r.ok) {
      const d = await r.json();
      const list = (d.list || []).map(it => ({
        ...it, vod_remarks: '暴風·' + (it.vod_remarks || ''),
      }));
      return json({
        code: 1, msg: 'Chill-AI-TV 推薦',
        page: 1, pagecount: Math.max(1, Math.ceil(list.length / 20)),
        limit: 20, total: list.length, list: list,
        class: d.class || [],
      });
    }
  } catch {}

  return json({ code: 0, msg: '暫無數據', list: [], class: [] });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' },
  });
}
