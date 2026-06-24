/**
 * Chill-AI-TV — Cloudflare Worker
 * 極簡代理：轉發所有請求到暴風
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // 健康檢查
    if (path === '/health') return new Response('OK', { status: 200 });

    // 靜態 JSON（config）
    if (path === '/' || path === '/api') {
      try {
        const apiUrl = 'https://api.github.com/repos/daicreation/DaiTVbobox/contents/output/config.json';
        const resp = await fetch(apiUrl, {
          headers: { 'User-Agent': 'ChillAITV/1.0', 'Accept': 'application/vnd.github.v3+json' },
        });
        const data = await resp.json();
        const binary = atob(data.content.replace(/\s/g, ''));
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        return new Response(new TextDecoder('utf-8').decode(bytes), {
          status: 200,
          headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=1800' },
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), { status: 503 });
      }
    }

    // 所有其他請求 → 轉發到暴風 API
    const target = 'https://bfzyapi.com/api.php/provide/vod' + url.search;
    try {
      const r = await fetch(target, {
        headers: { 'User-Agent': 'ChillAITV/1.0' },
        signal: AbortSignal.timeout(10000),
      });
      const body = await r.text();
      return new Response(body, {
        status: r.status,
        headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=300' },
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: e.message }), { status: 503 });
    }
  },
};
