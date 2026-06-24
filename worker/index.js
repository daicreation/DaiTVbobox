/**
 * Chill-AI-TV — Worker
 * Step 1: 7 直連站 + 聚合搜尋端點（不影響現有功能）
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const wd = url.searchParams.get('wd') || '';

    // 品牌聚合：瀏覽=暴風代理, 搜尋=多源
    if (path === '/search') {
      if (wd) return handleSearch(wd);
      return proxyBF();
    }

    // 現有 7 站直連（不變）
    return new Response(JSON.stringify({
      sites: [
        { key: "Chill", name: "🧊 Chill-AI-TV", type: 1, api: "https://daitvbobox.chungshare.workers.dev/search", searchable: 1, quickSearch: 1, filterable: 1 },
        { key: "bfzy", name: "🔥 暴風", type: 1, api: "https://bfzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
        { key: "ff",   name: "⚡ 非凡", type: 1, api: "http://cj.ffzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
        { key: "sn",   name: "🎯 索尼", type: 1, api: "https://suoniapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
        { key: "lz",   name: "🔮 量子", type: 1, api: "https://cj.lziapi.com/api.php/provide/vod/", searchable: 1, quickSearch: 1 },
        { key: "360",  name: "💠 360",  type: 1, api: "https://360zyzz.com/api.php/provide/vod/", searchable: 1, quickSearch: 1 },
        { key: "js",   name: "⚡ 極速", type: 1, api: "https://jszyapi.com/api.php/provide/vod/", searchable: 1, quickSearch: 1 },
        { key: "jy",   name: "🦅 金鷹", type: 1, api: "https://jyzyapi.com/provide/vod/", searchable: 1, quickSearch: 1 },
        { key: "xiaohezi", name: "📺 小盒子4K", type: 1, api: "http://xhztv.top/4k.json", searchable: 1, quickSearch: 1 },
        { key: "fantaiying", name: "🍚 飯太硬", type: 1, api: "https://qist.wyfc.qzz.io/fty.json", searchable: 1, quickSearch: 1 },
        { key: "xiaosa", name: "💨 瀟灑", type: 1, api: "https://qist.wyfc.qzz.io/xiaosa/api.json", searchable: 1, quickSearch: 1 },
      ],
      flags: ["4K","1080P","720P","優酷","愛奇藝","騰訊","芒果"],
    }), { status:200, headers:{ 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'no-cache' }});
  },
};

// ====== 瀏覽代理暴風（品牌首頁內容）======
async function proxyBF() {
  try {
    const r = await fetch('https://bfzyapi.com/api.php/provide/vod', { headers:{ 'User-Agent':'ChillAITV/1.0' }, signal:AbortSignal.timeout(8000) });
    if (!r.ok) return json({ code:0, list:[], class:[] });
    const data = await r.json();
    const bad = [29,73];
    if (data.list) data.list = data.list.filter(it => !bad.includes(it.type_id));
    if (data.class) data.class = data.class.filter(it => !bad.includes(it.type_id));
    return json(data);
  } catch { return json({ code:0, list:[], class:[] }); }
}

// ====== 聚合搜尋 ======
async function handleSearch(wd) {
  const sources = [
    { name:"🔥 暴風", api:"https://bfzyapi.com/api.php/provide/vod" },
    { name:"⚡ 非凡", api:"http://cj.ffzyapi.com/api.php/provide/vod" },
    { name:"🎯 索尼", api:"https://suoniapi.com/api.php/provide/vod" },
    { name:"🔮 量子", api:"https://cj.lziapi.com/api.php/provide/vod/" },
    { name:"💠 360",  api:"https://360zyzz.com/api.php/provide/vod/" },
    { name:"⚡ 極速", api:"https://jszyapi.com/api.php/provide/vod/" },
    { name:"🦅 金鷹", api:"https://jyzyapi.com/provide/vod/" },
  ];
  const results = await Promise.all(sources.map(async s => {
    try {
      const r = await fetch(`${s.api}?ac=detail&wd=${encodeURIComponent(wd)}`, { headers:{ 'User-Agent':'ChillAITV/1.0' }, signal:AbortSignal.timeout(6000) });
      if (!r.ok) return [];
      const d = await r.json();
      return (d.list||[]).map(it => ({ ...it, vod_remarks: s.name+"·"+(it.vod_remarks||'') }));
    } catch { return []; }
  }));
  const all = results.flat();
  const seen = new Set();
  const list = all.filter(it => {
    const k = ((it.vod_name||'')+'_'+(it.vod_year||'')).replace(/\s+/g,'').toLowerCase().slice(0,40);
    if (seen.has(k)||!k) return false;
    seen.add(k); return true;
  });
  return json({ code:1, msg:"Chill-AI-TV", page:1, pagecount:Math.max(1,Math.ceil(list.length/20)), limit:20, total:list.length, list:list.slice(0,100), class:[] });
}

function json(data, status=200) {
  return new Response(JSON.stringify(data), { status, headers:{ 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'public, max-age=300' }});
}
