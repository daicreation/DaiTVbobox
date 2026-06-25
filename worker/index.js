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

    // 品牌端點：純代理暴風（瀏覽 + 搜尋）
    if (path === '/api') return proxyBF(url.search);

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

async function proxyBF(search) {
  try {
    const r = await fetch('https://bfzyapi.com/api.php/provide/vod' + search, {
      headers: { 'User-Agent':'ChillAITV/1.0' }, signal: AbortSignal.timeout(10000),
    });
    if (!r.ok) return json({ code:0, list:[], class:[] });
    const data = await r.json();
    const bad = [29, 73];
    if (data.list) data.list = data.list.filter(it => !bad.includes(it.type_id));
    if (data.class) data.class = data.class.filter(it => !bad.includes(it.type_id));
    // 標記真實來源（海報下方顯示）
    if (data.list) data.list = data.list.map(it => ({
      ...it, vod_remarks: '暴風·' + (it.vod_remarks || ''),
    }));
    return json(data);
  } catch { return json({ code:0, list:[], class:[] }); }
}

function json(data, status=200) {
  return new Response(JSON.stringify(data), {
    status, headers:{ 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'public, max-age=300' },
  });
}
