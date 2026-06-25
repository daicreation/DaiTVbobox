/**
 * Chill-AI-TV — Cloudflare Worker
 * 先讀 GitHub Actions 生成的 config，讀不到就用內建備份
 */
// 內建備份（GitHub Actions 停擺時使用）
const FALLBACK = {
  sites: [
    { key: "Chill",      name: "🧊 Chill-TV", type: 1, api: "https://daitvbobox.chungshare.workers.dev/api", searchable: 1, quickSearch: 1, filterable: 1 },
    { key: "bfzy",       name: "🔥 暴風",     type: 1, api: "https://bfzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
    { key: "ff",         name: "⚡ 非凡",        type: 1, api: "http://cj.ffzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
    { key: "sn",         name: "🎯 索尼",        type: 1, api: "https://suoniapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
    { key: "lz",         name: "🔮 量子",        type: 1, api: "https://cj.lziapi.com/api.php/provide/vod/", searchable: 1, quickSearch: 1 },
    { key: "360",        name: "💠 360",         type: 1, api: "https://360zyzz.com/api.php/provide/vod/", searchable: 1, quickSearch: 1 },
    { key: "js",         name: "⚡ 極速",        type: 1, api: "https://jszyapi.com/api.php/provide/vod/", searchable: 1, quickSearch: 1 },
    { key: "jy",         name: "🦅 金鷹",        type: 1, api: "https://jyzyapi.com/provide/vod/", searchable: 1, quickSearch: 1 },
    { key: "xiaosa",     name: "💨 瀟灑",        type: 1, api: "https://qist.wyfc.qzz.io/xiaosa/api.json", searchable: 1, quickSearch: 1 },
    { key: "xiaopingguo",name: "🍎 小蘋果",      type: 1, api: "https://bitbucket.org/xduo/duoapi/raw/master/xpg.json", searchable: 1, quickSearch: 1 },
    { key: "moyuer",     name: "🐟 摸魚兒",      type: 1, api: "https://6800.kstore.vip/fish.json", searchable: 1, quickSearch: 1 },
    { key: "fantaiying", name: "🍚 飯太硬",      type: 1, api: "https://qist.wyfc.qzz.io/fty.json", searchable: 1, quickSearch: 1 },
  ],
  flags: ["4K","1080P","720P","優酷","愛奇藝","騰訊","芒果"],
};

// 品牌統一端點：瀏覽=暴風代理, 搜尋=聚合, 詳情=多源fallback
async function handleAll(url) {
  const wd = url.searchParams.get('wd') || '';
  const ac = url.searchParams.get('ac') || '';

  // 瀏覽模式 → 代理暴風（含分類+推薦）
  if (!wd && !ac) {
    try {
      const r = await fetch('https://bfzyapi.com/api.php/provide/vod', {
        headers: { 'User-Agent': 'ChillAITV/1.0' }, signal: AbortSignal.timeout(8000),
      });
      if (r.ok) {
        const data = await r.json();
        const bad = [29, 73];
        if (data.list) data.list = data.list.filter(it => !bad.includes(it.type_id));
        if (data.class) data.class = data.class.filter(it => !bad.includes(it.type_id));
        return json(data);
      }
    } catch {}
    return json({ code: 0, list: [], class: [] });
  }

  // 詳情模式 → 多源 fallback
  if (ac === 'videolist' || url.searchParams.get('ids')) {
    return handleDetail(url);
  }

  // 搜尋模式 → 聚合多源
  if (wd) return aggregateSearch(wd);

  return json({ code: 0, list: [], class: [] });
}

// 聚合搜尋：7 源並行查詢，去重合併
async function aggregateSearch(wd) {

  const sources = [
    { key: 'bfzy', name: '暴風', api: 'https://bfzyapi.com/api.php/provide/vod' },
    { key: 'ff',   name: '非凡', api: 'http://cj.ffzyapi.com/api.php/provide/vod' },
    { key: 'sn',   name: '索尼', api: 'https://suoniapi.com/api.php/provide/vod' },
    { key: 'lz',   name: '量子', api: 'https://cj.lziapi.com/api.php/provide/vod/' },
    { key: '360',  name: '360',  api: 'https://360zyzz.com/api.php/provide/vod/' },
    { key: 'js',   name: '極速', api: 'https://jszyapi.com/api.php/provide/vod/' },
    { key: 'jy',   name: '金鷹', api: 'https://jyzyapi.com/provide/vod/' },
  ];

  const results = await Promise.all(sources.map(async (s) => {
    try {
      const r = await fetch(`${s.api}?ac=detail&wd=${encodeURIComponent(wd)}`, {
        headers: { 'User-Agent': 'ChillAITV/1.0' }, signal: AbortSignal.timeout(6000),
      });
      if (!r.ok) return [];
      const d = await r.json();
      return (d.list || []).map(it => ({
        ...it,
        vod_remarks: `${s.name}·${it.vod_remarks || ''}`,
        _source: s.name,
        _key: s.key,
      }));
    } catch { return []; }
  }));

  const all = results.flat();
  const seen = new Set();
  const list = all.filter(it => {
    // 精準去重：片名 + 年份 + 類型（避免同名不同類誤合）
    const k = ((it.vod_name||'') + '|' + (it.vod_year||'') + '|' + (it.type_name||'')).replace(/\s+/g,'').toLowerCase().slice(0,60);
    if (seen.has(k) || !k) return false;
    seen.add(k);
    return true;
  });

  return json({
    code: 1, msg: `「${wd}」- ${list.length}結果`,
    page: 1, pagecount: Math.max(1, Math.ceil(list.length / 20)),
    limit: 20, total: list.length, list: list.slice(0, 100),
  });
}

// Phase 2: PlaybackPlan — 多源播放地址合併（$$$ 格式，依速度排序）
async function handleDetail(url) {
  const ids = url.searchParams.get('ids') || url.searchParams.get('id') || '';
  const name = url.searchParams.get('name') || '';
  if (!ids) return json({ code: 0, msg: 'Missing ids', list: [] });

  // 搜尋所有來源，找相同影片的播放地址
  const sources = [
    'https://bfzyapi.com/api.php/provide/vod',
    'https://cj.lziapi.com/api.php/provide/vod/',
    'https://360zyzz.com/api.php/provide/vod/',
    'https://jszyapi.com/api.php/provide/vod/',
    'https://jyzyapi.com/provide/vod/',
    'http://cj.ffzyapi.com/api.php/provide/vod',
    'https://suoniapi.com/api.php/provide/vod',
  ];

  // 並行查詢所有源的詳情
  const results = await Promise.all(sources.map(async (api) => {
    try {
      const start = Date.now();
      const r = await fetch(`${api}?ac=videolist&ids=${ids}`, {
        headers: { 'User-Agent': 'ChillAITV/1.0' },
        signal: AbortSignal.timeout(5000),
      });
      if (!r.ok) return null;
      const data = await r.json();
      const item = (data.list || [])[0];
      if (!item || !item.vod_play_url) return null;
      const srcName = new URL(api).hostname.replace('www.','').split('.')[0];
      return {
        name: srcName,
        speed: Date.now() - start,
        play_from: item.vod_play_from || srcName,
        play_url: item.vod_play_url,
      };
    } catch { return null; }
  }));

  // 過濾有效結果，按速度排序（快 → 慢）
  const valid = results.filter(r => r !== null);
  valid.sort((a, b) => a.speed - b.speed);

  if (valid.length === 0) {
    return json({ code: 0, msg: 'No play sources found', list: [] });
  }

  // 合併為 $$$ 格式
  const combined_from = valid.map(r => `${r.name}·HD`).join('$$$');
  const combined_url = valid.map(r => r.play_url).join('$$$');

  return json({
    code: 1,
    msg: `PlaybackPlan: ${valid.length} sources`,
    list: [{
      vod_id: ids,
      vod_name: name || ids,
      vod_play_from: combined_from,
      vod_play_url: combined_url,
      vod_remarks: `優:${valid[0].name}(${valid[0].speed}ms) +${valid.length-1}備`,
    }],
    sources: valid.map(r => ({ name: r.name, speed: r.speed })),
  });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // 品牌通用端點：瀏覽/搜尋/詳情
    if (path === '/api' || path === '/search') return handleAll(url);

    // 嘗試讀取 GitHub Actions 生成的最新 config
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
        // 確保有 sites 且非空
        if (config.sites && config.sites.length > 0) {
          return new Response(JSON.stringify(config), {
            status: 200,
            headers: { 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'no-cache' },
          });
        }
      }
    } catch {}

    // GitHub 讀不到 → 用內建備份
    return new Response(JSON.stringify(FALLBACK), {
      status: 200,
      headers: { 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'no-cache' },
    });
  },
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'public, max-age=300' },
  });
}
