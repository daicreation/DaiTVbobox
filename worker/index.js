/**
 * Chill-AI-TV — Cloudflare Worker
 * 7 站點直連，第一站為品牌名
 */
export default {
  async fetch(request, env, ctx) {
    return new Response(JSON.stringify({
      sites: [
        { key: "bfzy", name: "🧊 Chill-AI-TV", type: 1, api: "https://bfzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1, filterable: 1 },
        { key: "ff",   name: "⚡ 非凡", type: 1, api: "http://cj.ffzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
        { key: "sn",   name: "🎯 索尼", type: 1, api: "https://suoniapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
        { key: "lz",   name: "🔮 量子", type: 1, api: "https://cj.lziapi.com/api.php/provide/vod/", searchable: 1, quickSearch: 1 },
        { key: "360",  name: "💠 360",  type: 1, api: "https://360zyzz.com/api.php/provide/vod/", searchable: 1, quickSearch: 1 },
        { key: "js",   name: "⚡ 極速", type: 1, api: "https://jszyapi.com/api.php/provide/vod/", searchable: 1, quickSearch: 1 },
        { key: "jy",   name: "🦅 金鷹", type: 1, api: "https://jyzyapi.com/provide/vod/", searchable: 1, quickSearch: 1 },
        { key: "xiaosa",     name: "💨 瀟灑(121)", type: 1, api: "https://qist.wyfc.qzz.io/xiaosa/api.json", searchable: 1, quickSearch: 1 },
        { key: "xiaopingguo",name: "🍎 小蘋果(136)",type: 1, api: "https://bitbucket.org/xduo/duoapi/raw/master/xpg.json", searchable: 1, quickSearch: 1 },
        { key: "moyuer",     name: "🐟 摸魚兒(87)", type: 1, api: "https://6800.kstore.vip/fish.json", searchable: 1, quickSearch: 1 },
        { key: "fantaiying", name: "🍚 飯太硬(48)", type: 1, api: "https://qist.wyfc.qzz.io/fty.json", searchable: 1, quickSearch: 1 },
      ],
      flags: ["4K","1080P","720P","優酷","愛奇藝","騰訊","芒果"],
    }), {
      status: 200,
      headers: { 'Content-Type':'application/json; charset=utf-8', 'Access-Control-Allow-Origin':'*', 'Cache-Control':'no-cache' },
    });
  },
};
