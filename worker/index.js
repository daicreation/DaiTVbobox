/**
 * DaiTVbobox — Cloudflare Worker (GitHub API 版，無 CDN 快取問題)
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // GitHub API 基礎 URL（無 CDN 快取）
    const API = 'https://api.github.com/repos/daicreation/DaiTVbobox/contents';

    // 路由表：路徑 → GitHub 檔案路徑
    const routes = {
      '/':            '/output/config.json',
      '/api':         '/output/config.json',
      '/movie':       '/output/movie.json',
      '/tv':          '/output/tv.json',
      '/variety':     '/output/variety.json',
      '/live':        '/output/live.json',
      '/spider.jar':  '/spider/spider.jar',
    };

    // 健康檢查
    if (path === '/health') {
      return new Response('OK', {
        status: 200,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
      });
    }

    // 路由處理
    const filePath = routes[path];
    if (!filePath) {
      return new Response(JSON.stringify({ error: 'Not Found', paths: Object.keys(routes) }), {
        status: 404,
        headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' },
      });
    }

    // 從 GitHub API 獲取內容
    try {
      const apiUrl = API + filePath;
      const resp = await fetch(apiUrl, {
        headers: {
          'User-Agent': 'DaiTVbobox/1.0',
          'Accept': 'application/vnd.github.v3+json',
        },
      });

      if (!resp.ok) {
        return new Response(JSON.stringify({ error: 'Upstream', status: resp.status }), {
          status: 502,
          headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' },
        });
      }

      const data = await resp.json();
      // GitHub API 返回 base64 編碼的內容
      const content = atob(data.content.replace(/\s/g, ''));
      const ct = path.endsWith('.jar') ? 'application/java-archive' : 'application/json; charset=utf-8';

      return new Response(content, {
        status: 200,
        headers: {
          'Content-Type': ct,
          'Access-Control-Allow-Origin': '*',
          'Cache-Control': 'public, max-age=1800',
        },
      });
    } catch (err) {
      return new Response(JSON.stringify({ error: 'Fetch failed', message: err.message }), {
        status: 503,
        headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' },
      });
    }
  },
};
