/**
 * Chill-AI-TV — Cloudflare Worker
 * 先讀 GitHub Actions 生成的 config，讀不到就用內建備份
 */
// 內建備份（GitHub Actions 停擺時使用）
const FALLBACK = {
  sites: [
    { key: "bfzy",       name: "🧊 Chill-AI-TV", type: 1, api: "https://bfzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
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

export default {
  async fetch(request, env, ctx) {
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
