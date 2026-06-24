/**
 * Chill-AI-TV — Cloudflare Worker
 * 只發 config，16 站點直連（確定能用的版本）
 */
export default {
  async fetch(request, env, ctx) {
    const DOMAIN = 'https://daitvbobox.chungshare.workers.dev';
    return new Response(JSON.stringify({
      sites: [
        { key: "bfzy",       name: "🔥 暴風",     type: 1, api: "https://bfzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
        { key: "ff",         name: "⚡ 非凡",     type: 1, api: "http://cj.ffzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
        { key: "sn",         name: "🎯 索尼",     type: 1, api: "https://suoniapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
        { key: "xiaosa",     name: "💨 瀟灑(121)", type: 1, api: "https://qist.wyfc.qzz.io/xiaosa/api.json", searchable: 1, quickSearch: 1 },
        { key: "xiaopingguo",name: "🍎 小蘋果(136)",type: 1, api: "https://bitbucket.org/xduo/duoapi/raw/master/xpg.json", searchable: 1, quickSearch: 1 },
        { key: "moyuer",     name: "🐟 摸魚兒(87)",type: 1, api: "https://6800.kstore.vip/fish.json", searchable: 1, quickSearch: 1 },
        { key: "wangerxiao", name: "👦 王二小(85)",type: 1, api: "https://9280.kstore.vip/newwex.json", searchable: 1, quickSearch: 1 },
        { key: "fmys",       name: "🐴 fmys(82)", type: 1, api: "http://fmys.top/fmys.json", searchable: 1, quickSearch: 1 },
        { key: "fantaiying", name: "🍚 飯太硬(48)",type: 1, api: "https://qist.wyfc.qzz.io/fty.json", searchable: 1, quickSearch: 1 },
        { key: "ok",         name: "👌 OK(45)",    type: 1, api: "https://gist.githubusercontent.com/ph7368/20ee6c7b64d77d82f8f4162cdd04ad61/raw/gistfile1.txt", searchable: 1, quickSearch: 1 },
        { key: "jianpian",   name: "🎬 荐片(28)",  type: 1, api: "https://tv.203511.xyz/0821.json", searchable: 1, quickSearch: 1 },
      ],
      flags: ["4K", "1080P", "720P", "優酷", "愛奇藝", "騰訊", "芒果"],
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=1800' },
    });
  },
};
