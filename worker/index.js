/**
 * Chill-AI-TV vFinal
 * 🧊 Chill-TV = 暴風全代理（瀏覽分類 + 搜尋）
 * 其他站點 = 直連備用
 */
const DOMAIN = 'https://daitvbobox.chungshare.workers.dev';

function buildFallback(region = 'hk') {
  const base = `${DOMAIN}/${region}`;
  return {
    sites: [
      { key:"chill", name:"🧊 Chill-TV", type:1, api: `${base}/api`, searchable:1, quickSearch:1, filterable:1 },
      { key:"bfzy",  name:"🔥 暴風",    type:1, api: `${base}/p/bfzy`, searchable:1, quickSearch:1 },
      { key:"ff",    name:"⚡ 非凡",    type:1, api: `${base}/p/ff`, searchable:1, quickSearch:1 },
      { key:"sn",    name:"🎯 索尼",    type:1, api: `${base}/p/sn`, searchable:1, quickSearch:1 },
      { key:"lz",    name:"🔮 量子",    type:1, api: `${base}/p/lz`, searchable:1, quickSearch:1 },
      { key:"360",   name:"💠 360",     type:1, api: `${base}/p/360`, searchable:1, quickSearch:1 },
      { key:"js",    name:"⚡ 極速",    type:1, api: `${base}/p/js`, searchable:1, quickSearch:1 },
      { key:"jy",    name:"🦅 金鷹",    type:1, api: `${base}/p/jy`, searchable:1, quickSearch:1 },
      { key:"wj",    name:"♾️ 無盡",    type:1, api: `${base}/p/wj`, searchable:1, quickSearch:1 },
      { key:"yh",    name:"🌸 櫻花",    type:1, api: `${base}/p/yh`, searchable:1, quickSearch:1 },
      { key:"md",    name:"🏙️ 魔都",    type:1, api: `${base}/p/md`, searchable:1, quickSearch:1 },
      { key:"ik",    name:"🎵 iKun",    type:1, api: `${base}/p/ik`, searchable:1, quickSearch:1 },
    ],
    flags: ["4K","1080P","720P","優酷","愛奇藝","騰訊","芒果"],
    region,
  };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const route = parseRoute(url.pathname);

    if (route.kind === 'api') return proxyBrowse(url.search);

    if (route.kind === 'proxy') return proxyFiltered(route.proxyKey, url.search);

    try {
      const configFile = route.region === 'cn' ? 'config.cn.json' : 'config.hk.json';
      const apiUrl = `https://api.github.com/repos/daicreation/DaiTVbobox/contents/output/${configFile}`;
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
          config.sites = config.sites.filter(s => !(s.name||'').includes('采集'));
          return new Response(JSON.stringify(config), {
            status:200,
            headers:{ 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'no-cache' },
          });
        }
      }
    } catch {}

    return new Response(JSON.stringify(buildFallback(route.region)), {
      status:200,
      headers:{ 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'no-cache' },
    });
  },
};

function parseRoute(pathname) {
  const parts = pathname.split('/').filter(Boolean);
  const first = parts[0] || '';
  const region = first === 'cn' ? 'cn' : 'hk';
  const offset = (first === 'hk' || first === 'cn') ? 1 : 0;
  const next = parts[offset] || '';

  if (next === 'api') {
    return { region, kind: 'api', proxyKey: '' };
  }

  if (next === 'p' && parts[offset + 1]) {
    return { region, kind: 'proxy', proxyKey: parts[offset + 1] };
  }

  return { region, kind: 'config', proxyKey: '' };
}

// /p/xxx -> 對應 API（全部過濾成人內容）
const PROXY_MAP = {
  bfzy: 'https://bfzyapi.com/api.php/provide/vod',
  ff:   'http://cj.ffzyapi.com/api.php/provide/vod',
  sn:   'https://suoniapi.com/api.php/provide/vod',
  lz:   'https://cj.lziapi.com/api.php/provide/vod/',
  360:  'https://360zyzz.com/api.php/provide/vod/',
  js:   'https://jszyapi.com/api.php/provide/vod/',
  jy:   'https://jyzyapi.com/provide/vod/',
  wj:   'https://api.wujinapi.me/api.php/provide/vod',
  yh:   'https://m3u8.apiyhzy.com/api.php/provide/vod',
  md:   'https://www.mdzyapi.com/api.php/provide/vod',
  ik:   'https://ikunzyapi.com/api.php/provide/vod',
};

async function proxyFiltered(key, search) {
  const target = PROXY_MAP[key];
  if (!target) return json({ code:0, list:[], class:[] });
  return proxyBrowse(search, target);
}

async function proxyBrowse(search = '', target) {
  const api = target || 'https://bfzyapi.com/api.php/provide/vod';
  try {
    const r = await fetch(api + search, {
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

function json(data, status=200) {
  return new Response(JSON.stringify(data), {
    status,
    headers:{ 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'public, max-age=300' },
  });
}
