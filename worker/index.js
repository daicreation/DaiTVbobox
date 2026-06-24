/**
 * Chill-AI-TV — 帶子站點的聚合模式
 * Worker 回傳內容 + sites 陣列，TVBox 自動跨子站搜尋（用你的 IP）
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === '/health') return new Response('OK', { status: 200 });

    // Config
    if (path === '/' || path === '/api') return serveConfig();

    // 主 API：回傳首頁內容 + 子站點列表
    return serveAPI(url);
  },
};

async function serveConfig() {
  const resp = await fetch('https://api.github.com/repos/daicreation/DaiTVbobox/contents/output/config.json', {
    headers: { 'User-Agent': 'ChillAITV/1.0', 'Accept': 'application/vnd.github.v3+json' },
  });
  const data = await resp.json();
  const binary = atob(data.content.replace(/\s/g, ''));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Response(new TextDecoder('utf-8').decode(bytes), {
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=1800' },
  });
}

async function serveAPI(url) {
  // 子站點列表（TVBox 會自動用你的 IP 搜這些）
  const subSites = [
    { key: "bfzy", name: "🔥 暴風", type: 1, api: "https://bfzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
    { key: "hwk",  name: "🌏 海外看", type: 1, api: "https://haiwaikan.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
    { key: "ff",   name: "⚡ 非凡", type: 1, api: "http://cj.ffzyapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
    { key: "sn",   name: "🎯 索尼", type: 1, api: "https://suoniapi.com/api.php/provide/vod", searchable: 1, quickSearch: 1 },
    { key: "fantaiying", name: "🍚 飯太硬", type: 1, api: "https://qist.wyfc.qzz.io/fty.json", searchable: 1, quickSearch: 1 },
    { key: "xiaosa", name: "💨 瀟灑", type: 1, api: "https://qist.wyfc.qzz.io/xiaosa/api.json", searchable: 1, quickSearch: 1 },
    { key: "liu", name: "📦 liu673cn", type: 1, api: "https://cdn.jsdelivr.net/gh/liu673cn/box@main/m.json", searchable: 1, quickSearch: 1 },
    { key: "moyuer", name: "🐟 摸魚兒", type: 1, api: "https://6800.kstore.vip/fish.json", searchable: 1, quickSearch: 1 },
    { key: "feimao", name: "🐱 肥貓", type: 1, api: "http://feimao.pro", searchable: 1, quickSearch: 1 },
    { key: "ok", name: "👌 OK", type: 1, api: "https://gist.githubusercontent.com/ph7368/20ee6c7b64d77d82f8f4162cdd04ad61/raw/gistfile1.txt", searchable: 1, quickSearch: 1 },
    { key: "xiaohezi", name: "📺 小盒子4K", type: 1, api: "http://xhztv.top/4k.json", searchable: 1, quickSearch: 1 },
    { key: "jianpian", name: "🎬 荐片", type: 1, api: "https://tv.203511.xyz/0821.json", searchable: 1, quickSearch: 1 },
  ];

  // 抓取暴風首頁內容（快取 5 分鐘）
  try {
    const r = await fetch('https://bfzyapi.com/api.php/provide/vod' + url.search, {
      headers: { 'User-Agent': 'ChillAITV/1.0' },
      signal: AbortSignal.timeout(8000),
    });
    if (r.ok) {
      const data = await r.json();
      // 過濾成人分類 + 注入子站點
      const blocked = [29, 73];
      if (data.list) data.list = data.list.filter(it => !blocked.includes(it.type_id));
      if (data.class) data.class = data.class.filter(it => !blocked.includes(it.type_id));
      data.sites = subSites; // 關鍵：讓 TVBox 跨子站搜尋
      return new Response(JSON.stringify(data), {
        headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=300' },
      });
    }
  } catch {}

  // Fallback
  return new Response(JSON.stringify({ code: 1, msg: 'Chill-AI-TV', list: [], class: [], sites: subSites }), {
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=300' },
  });
}
