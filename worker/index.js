/**
 * Chill-AI-TV — Worker (多倉模式)
 * /       → 主 config（storeHouse 多倉）
 * /bfzy   → 暴風子倉
 * /misc   → 其他子倉
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const DOMAIN = 'https://daitvbobox.chungshare.workers.dev';

    // 主 config（urls 多倉格式）
    if (path === '/' || path === '/api') {
      return json({
        urls: [
          { url: DOMAIN + "/bfzy",        name: "🔥 暴風" },
          { url: DOMAIN + "/hwk",         name: "🌏 海外看" },
          { url: DOMAIN + "/ff",          name: "⚡ 非凡" },
          { url: DOMAIN + "/sn",          name: "🎯 索尼" },
          { url: DOMAIN + "/fantaiying",  name: "🍚 飯太硬" },
          { url: DOMAIN + "/xiaosa",      name: "💨 瀟灑" },
          { url: DOMAIN + "/liu",         name: "📦 liu673cn" },
          { url: DOMAIN + "/moyuer",      name: "🐟 摸魚兒" },
          { url: DOMAIN + "/feimao",      name: "🐱 肥貓" },
          { url: DOMAIN + "/ok",          name: "👌 OK" },
          { url: DOMAIN + "/wangerxiao",  name: "👦 王二小" },
          { url: DOMAIN + "/xiaohezi",    name: "📺 小盒子4K" },
          { url: DOMAIN + "/jianpian",    name: "🎬 荐片" },
          { url: DOMAIN + "/fmys",        name: "🐴 fmys" },
          { url: DOMAIN + "/jundie",      name: "👨 俊哥" },
          { url: DOMAIN + "/xiaopingguo", name: "🍎 小蘋果" },
        ],
        flags: ["4K", "1080P", "720P", "優酷", "愛奇藝", "騰訊", "芒果"],
      });
    }

    // 各子倉 → 回傳 sites
    const subConfigs = {
      '/bfzy':        [{ key: "bfzy", name: "🔥 暴風",     type: 1, api: "https://bfzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 }],
      '/hwk':         [{ key: "hwk",  name: "🌏 海外看",   type: 1, api: "https://haiwaikan.com/api.php/provide/vod", searchable: 1, quickSearch: 1 }],
      '/ff':          [{ key: "ff",   name: "⚡ 非凡",     type: 1, api: "http://cj.ffzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 }],
      '/sn':          [{ key: "sn",   name: "🎯 索尼",     type: 1, api: "https://suoniapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 }],
      '/fantaiying':  [{ key: "fantaiying", name: "🍚 飯太硬", type: 1, api: "https://qist.wyfc.qzz.io/fty.json", searchable: 1, quickSearch: 1 }],
      '/xiaosa':      [{ key: "xiaosa", name: "💨 瀟灑",   type: 1, api: "https://qist.wyfc.qzz.io/xiaosa/api.json", searchable: 1, quickSearch: 1 }],
      '/liu':         [{ key: "liu",  name: "📦 liu673cn", type: 1, api: "https://cdn.jsdelivr.net/gh/liu673cn/box@main/m.json", searchable: 1, quickSearch: 1 }],
      '/moyuer':      [{ key: "moyuer", name: "🐟 摸魚兒", type: 1, api: "https://6800.kstore.vip/fish.json", searchable: 1, quickSearch: 1 }],
      '/feimao':      [{ key: "feimao", name: "🐱 肥貓",   type: 1, api: "http://feimao.pro", searchable: 1, quickSearch: 1 }],
      '/ok':          [{ key: "ok",   name: "👌 OK",       type: 1, api: "https://gist.githubusercontent.com/ph7368/20ee6c7b64d77d82f8f4162cdd04ad61/raw/gistfile1.txt", searchable: 1, quickSearch: 1 }],
      '/wangerxiao':  [{ key: "wangerxiao", name: "👦 王二小",   type: 1, api: "https://9280.kstore.vip/newwex.json", searchable: 1, quickSearch: 1 }],
      '/xiaohezi':    [{ key: "xiaohezi", name: "📺 小盒子4K",   type: 1, api: "http://xhztv.top/4k.json", searchable: 1, quickSearch: 1 }],
      '/jianpian':    [{ key: "jianpian", name: "🎬 荐片",       type: 1, api: "https://tv.203511.xyz/0821.json", searchable: 1, quickSearch: 1 }],
      '/fmys':        [{ key: "fmys", name: "🐴 fmys",     type: 1, api: "http://fmys.top/fmys.json", searchable: 1, quickSearch: 1 }],
      '/jundie':      [{ key: "jundie", name: "👨 俊哥",   type: 1, api: "http://home.jundie.top:81/top98.json", searchable: 1, quickSearch: 1 }],
      '/xiaopingguo': [{ key: "xiaopingguo", name: "🍎 小蘋果", type: 1, api: "https://bitbucket.org/xduo/duoapi/raw/master/xpg.json", searchable: 1, quickSearch: 1 }],
    };

    if (subConfigs[path]) {
      return json({ sites: subConfigs[path] });
    }

    return json({ error: 'Not Found' }, 404);
  },
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=1800' },
  });
}
