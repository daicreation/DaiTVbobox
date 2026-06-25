/**
 * Chill-AI-TV vFinal
 * 🧊 Chill-TV = 暴風全代理（瀏覽分類 + 搜尋）
 * 其他站點 = 直連備用
 */
const DOMAIN = 'https://daitvbobox.chungshare.workers.dev';

const FALLBACK = {
  sites: [
    { key:"Chill", name:"🧊 Chill-TV", type:1, api: DOMAIN + "/api", searchable:1, quickSearch:1, filterable:1 },
    { key:"bfzy",  name:"🔥 暴風",    type:1, api:"https://bfzyapi.com/api.php/provide/vod", searchable:1, quickSearch:1 },
    { key:"ff",    name:"⚡ 非凡",    type:1, api:"http://cj.ffzyapi.com/api.php/provide/vod", searchable:1, quickSearch:1 },
    { key:"sn",    name:"🎯 索尼",    type:1, api:"https://suoniapi.com/api.php/provide/vod", searchable:1, quickSearch:1 },
    { key:"lz",    name:"🔮 量子",    type:1, api:"https://cj.lziapi.com/api.php/provide/vod/", searchable:1, quickSearch:1 },
    { key:"360",   name:"💠 360",     type:1, api:"https://360zyzz.com/api.php/provide/vod/", searchable:1, quickSearch:1 },
    { key:"js",    name:"⚡ 極速",    type:1, api:"https://jszyapi.com/api.php/provide/vod/", searchable:1, quickSearch:1 },
    { key:"jy",    name:"🦅 金鷹",    type:1, api:"https://jyzyapi.com/provide/vod/", searchable:1, quickSearch:1 },
    { key:"wj",    name:"♾️ 無盡",    type:1, api:"https://api.wujinapi.me/api.php/provide/vod", searchable:1, quickSearch:1 },
    { key:"yh",    name:"🌸 櫻花",    type:1, api:"https://m3u8.apiyhzy.com/api.php/provide/vod", searchable:1, quickSearch:1 },
    { key:"md",    name:"🏙️ 魔都",    type:1, api:"https://www.mdzyapi.com/api.php/provide/vod", searchable:1, quickSearch:1 },
    { key:"ik",    name:"🎵 iKun",    type:1, api:"https://ikunzyapi.com/api.php/provide/vod", searchable:1, quickSearch:1 },
    { key:"xiaosa",name:"💨 瀟灑",    type:1, api:"https://qist.wyfc.qzz.io/xiaosa/api.json", searchable:1, quickSearch:1 },
    { key:"xiaopingguo",name:"🍎 小蘋果",type:1, api:"https://bitbucket.org/xduo/duoapi/raw/master/xpg.json", searchable:1, quickSearch:1 },
    { key:"moyuer",name:"🐟 摸魚兒",  type:1, api:"https://6800.kstore.vip/fish.json", searchable:1, quickSearch:1 },
    { key:"fantaiying",name:"🍚 飯太硬",type:1, api:"https://qist.wyfc.qzz.io/fty.json", searchable:1, quickSearch:1 },
  ],
  flags: ["4K","1080P","720P","優酷","愛奇藝","騰訊","芒果"],
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // 品牌端點：瀏覽=暴風，搜尋=聚合，詳情=fallback
    if (path === '/api') {
      const wd = url.searchParams.get('wd') || '';
      const ac = url.searchParams.get('ac') || '';
      // 詳情請求 → 多源 fallback
      if (ac === 'videolist' || url.searchParams.get('ids')) return handleDetail(url);
      // 搜尋 → 11 源聚合
      if (wd) return aggregateSearch(wd);
      // 瀏覽 → 暴風代理
      return proxyBrowse();
    }

    // 先讀 GitHub config
    try {
      const apiUrl = 'https://api.github.com/repos/daicreation/DaiTVbobox/contents/output/config.json';
      const resp = await fetch(apiUrl, {
        headers: { 'User-Agent':'ChillAITV/1.0', 'Accept':'application/vnd.github.v3+json' },
      });
      if (resp.ok) {
        const data = await resp.json();
        const binary = atob(data.content.replace(/\s/g, ''));
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        const config = JSON.parse(new TextDecoder('utf-8').decode(bytes));
        if (config.sites?.length > 0) {
          return new Response(JSON.stringify(config), {
            status:200, headers:{ 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'no-cache' },
          });
        }
      }
    } catch {}

    return new Response(JSON.stringify(FALLBACK), {
      status:200, headers:{ 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'no-cache' },
    });
  },
};

async function proxyBrowse() {
  try {
    const r = await fetch('https://bfzyapi.com/api.php/provide/vod', {
      headers: { 'User-Agent':'ChillAITV/1.0' }, signal: AbortSignal.timeout(8000),
    });
    if (!r.ok) return json({ code:0, list:[], class:[] });
    const data = await r.json();
    const bad = [29, 73];
    if (data.list) data.list = data.list.filter(it => !bad.includes(it.type_id));
    if (data.class) data.class = data.class.filter(it => !bad.includes(it.type_id));
    return json(data);
  } catch { return json({ code:0, list:[], class:[] }); }
}

// 聚合搜尋 — 11 源並行
async function aggregateSearch(wd) {
  const sources = [
    { key:"bfzy", name:"暴風", api:"https://bfzyapi.com/api.php/provide/vod" },
    { key:"ff",   name:"非凡", api:"http://cj.ffzyapi.com/api.php/provide/vod" },
    { key:"sn",   name:"索尼", api:"https://suoniapi.com/api.php/provide/vod" },
    { key:"lz",   name:"量子", api:"https://cj.lziapi.com/api.php/provide/vod/" },
    { key:"360",  name:"360",  api:"https://360zyzz.com/api.php/provide/vod/" },
    { key:"js",   name:"極速", api:"https://jszyapi.com/api.php/provide/vod/" },
    { key:"jy",   name:"金鷹", api:"https://jyzyapi.com/provide/vod/" },
    { key:"wj",   name:"無盡", api:"https://api.wujinapi.me/api.php/provide/vod" },
    { key:"yh",   name:"櫻花", api:"https://m3u8.apiyhzy.com/api.php/provide/vod" },
    { key:"md",   name:"魔都", api:"https://www.mdzyapi.com/api.php/provide/vod" },
    { key:"ik",   name:"iKun", api:"https://ikunzyapi.com/api.php/provide/vod" },
  ];
  const results = await Promise.all(sources.map(async s => {
    try {
      const r = await fetch(`${s.api}?ac=detail&wd=${encodeURIComponent(wd)}`, {
        headers:{ 'User-Agent':'ChillAITV/1.0' }, signal:AbortSignal.timeout(6000),
      });
      if (!r.ok) return [];
      const d = await r.json();
      return (d.list||[]).map(it => ({
        ...it, vod_remarks: s.name+'·'+(it.vod_remarks||''),
      }));
    } catch { return []; }
  }));
  const all = results.flat();
  const seen = new Set();
  const list = all.filter(it => {
    const k = ((it.vod_name||'')+'|'+(it.vod_year||'')+'|'+(it.type_name||'')).replace(/\s+/g,'').toLowerCase().slice(0,60);
    if (seen.has(k)||!k) return false;
    seen.add(k); return true;
  });
  return json({ code:1, msg:`「${wd}」- ${list.length}結果`, page:1, pagecount:Math.max(1,Math.ceil(list.length/20)), limit:20, total:list.length, list:list.slice(0,100) });
}

// PlaybackPlan — 多源播放 fallback
async function handleDetail(url) {
  const ids = url.searchParams.get('ids')||url.searchParams.get('id')||'';
  if (!ids) return json({ code:0, msg:'Missing ids', list:[] });
  const apis = [
    'https://suoniapi.com/api.php/provide/vod',
    'https://bfzyapi.com/api.php/provide/vod',
    'https://cj.lziapi.com/api.php/provide/vod/',
    'https://360zyzz.com/api.php/provide/vod/',
    'https://jszyapi.com/api.php/provide/vod/',
    'https://jyzyapi.com/provide/vod/',
    'http://cj.ffzyapi.com/api.php/provide/vod',
  ];
  const results = await Promise.all(apis.map(async api => {
    try {
      const start = Date.now();
      const r = await fetch(`${api}?ac=videolist&ids=${ids}`, { headers:{ 'User-Agent':'ChillAITV/1.0' }, signal:AbortSignal.timeout(5000) });
      if (!r.ok) return null;
      const d = await r.json();
      const it = (d.list||[])[0];
      if (!it?.vod_play_url) return null;
      return { name:new URL(api).hostname.split('.')[0], speed:Date.now()-start, url:it.vod_play_url };
    } catch { return null; }
  }));
  const valid = results.filter(r=>r!==null).sort((a,b)=>a.speed-b.speed);
  if (!valid.length) return json({ code:0, msg:'No sources', list:[] });
  const from = valid.map(r=>r.name+'·HD').join('$$$');
  const urls = valid.map(r=>r.url).join('$$$');
  return json({ code:1, msg:`${valid.length}源`, list:[{ vod_id:ids, vod_play_from:from, vod_play_url:urls, vod_remarks:`優:${valid[0].name}(${valid[0].speed}ms)+${valid.length-1}備` }] });
}

function json(data, status=200) {
  return new Response(JSON.stringify(data), {
    status, headers:{ 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'public, max-age=300' },
  });
}
