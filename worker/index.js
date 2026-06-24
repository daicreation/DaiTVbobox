/**
 * DaiTVbobox — Cloudflare Worker (最簡版，確保可運行)
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // GitHub Raw 基礎 URL
    const BASE = 'https://raw.githubusercontent.com/daicreation/DaiTVbobox/main/output';

    // 路由表
    const routes = {
      '/':         BASE + '/config.json',
      '/api':      BASE + '/config.json',
      '/movie':    BASE + '/movie.json',
      '/tv':       BASE + '/tv.json',
      '/variety':  BASE + '/variety.json',
      '/live':     BASE + '/live.json',
    };

    // 健康檢查
    if (path === '/health') {
      return new Response('OK', {
        status: 200,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
      });
    }

    // 路由處理
    const targetUrl = routes[path];
    if (!targetUrl) {
      return new Response(JSON.stringify({
        error: 'Not Found',
        paths: Object.keys(routes),
      }), {
        status: 404,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Access-Control-Allow-Origin': '*',
        },
      });
    }

    // 從 GitHub 獲取內容
    try {
      const response = await fetch(targetUrl, {
        headers: { 'User-Agent': 'DaiTVbobox/1.0' },
      });

      if (!response.ok) {
        return new Response(JSON.stringify({
          error: 'Upstream error',
          status: response.status,
        }), {
          status: 502,
          headers: {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
          },
        });
      }

      // 回傳結果
      return new Response(response.body, {
        status: 200,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Access-Control-Allow-Origin': '*',
          'Cache-Control': 'public, max-age=3600',
        },
      });
    } catch (err) {
      return new Response(JSON.stringify({
        error: 'Fetch failed',
        message: err.message,
      }), {
        status: 503,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Access-Control-Allow-Origin': '*',
        },
      });
    }
  },
};
