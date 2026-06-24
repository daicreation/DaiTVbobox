/**
 * Chill-AI-TV — Cloudflare Worker
 * 只負責發 config.json，不代理 API
 * TVBox 用自己的 IP 直連各站點（像寶盒一樣）
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === '/health') return new Response('OK', { status: 200 });

    // 所有請求 → 回傳 config.json
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
  },
};
