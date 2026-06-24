/**
 * Chill-AI-TV — Worker (聚合引擎)
 * /api.php/provide/vod → 瀏覽=暴風, 搜尋=聚合多源
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const wd = url.searchParams.get('wd') || '';

    if (path === '/health') return new Response('OK', { status: 200 });

    // 首頁 config
    if (path === '/' || path === '/api') {
      return json({
        sites: [{
          key: "Chill_AI_TV",
          name: "🧊 Chill-AI-TV",
          type: 1,
          api: "https://daitvbobox.chungshare.workers.dev/api.php/provide/vod",
          searchable: 1, quickSearch: 1, filterable: 1,
        }],
        flags: ["4K", "1080P", "720P", "優酷", "愛奇藝", "騰訊", "芒果"],
      });
    }

    // API 端點
    if (path === '/api.php/provide/vod') {
      if (wd) return handleSearch(wd);
      return proxyBrowse();
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
    { name: "🔥 暴風",   api: "https://bfzyapi.com/api.php/provide/vod" },
    { name: "⚡ 非凡",   api: "http://cj.ffzyapi.com/api.php/provide/vod" },
    { name: "🎯 索尼",   api: "https://suoniapi.com/api.php/provide/vod" },
    { name: "🔮 量子",   api: "https://cj.lziapi.com/api.php/provide/vod/" },
    { name: "💠 360",    api: "https://360zyzz.com/api.php/provide/vod/" },
    { name: "⚡ 極速",   api: "https://jszyapi.com/api.php/provide/vod/" },
    { name: "🦅 金鷹",   api: "https://jyzyapi.com/provide/vod/" },
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
        ...it, _source: src.name,
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

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=300' },
  });
}
