/**
 * DaiTVbobox — Cloudflare Worker (API 代理版)
 * HK + 大陸 雙邊可用
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    const API = 'https://api.github.com/repos/daicreation/DaiTVbobox/contents';

    // ---- API 代理：TVBox 發來的站點查詢 ----
    if (path === '/proxy') {
      return handleProxy(request);
    }

    // ---- 路由表 ----
    const routes = {
      '/':            '/output/config.json',
      '/api':         '/output/config.json',
      '/movie':       '/output/movie.json',
      '/tv':          '/output/tv.json',
      '/variety':     '/output/variety.json',
      '/live':        '/output/live.json',
    };

    // 健康檢查
    if (path === '/health') {
      return new Response('OK', { status: 200, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }

    const filePath = routes[path];
    if (!filePath) {
      return new Response(JSON.stringify({ error: 'Not Found' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' },
      });
    }

    // ---- 從 GitHub API 讀取 JSON ----
    try {
      const resp = await fetch(API + filePath, {
        headers: { 'User-Agent': 'ChillAITV/1.0', 'Accept': 'application/vnd.github.v3+json' },
      });
      if (!resp.ok) {
        return new Response(JSON.stringify({ error: 'Upstream', status: resp.status }), {
          status: 502, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' },
        });
      }
      const data = await resp.json();
      // 正確 UTF-8 解碼
      const binary = atob(data.content.replace(/\s/g, ''));
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const content = new TextDecoder('utf-8').decode(bytes);

      return new Response(content, {
        status: 200,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Access-Control-Allow-Origin': '*',
          'Cache-Control': 'public, max-age=1800',
        },
      });
    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 503, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' },
      });
    }
  },
};

/**
 * API 代理：轉發 TVBox 的站點查詢請求
 *
 * TVBox 請求格式：/proxy?url=http://example.com/api.php/provide/vod/&t=search&wd=xxx
 * Worker 代為請求真實 API，回傳結果
 */
async function handleProxy(request) {
  const url = new URL(request.url);
  const target = url.searchParams.get('url');

  if (!target) {
    return new Response(JSON.stringify({ error: 'Missing url param' }), {
      status: 400, headers: { 'Content-Type': 'application/json; charset=utf-8' },
    });
  }

  // 解碼目標 URL 並保留 TVBox 傳來的其他參數
  const decodedTarget = decodeURIComponent(target);
  const targetUrl = new URL(decodedTarget);
  for (const [key, value] of url.searchParams) {
    if (key !== 'url') targetUrl.searchParams.set(key, value);
  }

  try {
    const resp = await fetch(targetUrl.toString(), {
      headers: {
        'User-Agent': 'ChillAITV-Proxy/1.0',
        'Accept': 'application/json, text/plain, */*',
      },
    });

    const body = await resp.text();

    return new Response(body, {
      status: resp.status,
      headers: {
        'Content-Type': resp.headers.get('Content-Type') || 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'public, max-age=300',
      },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: 'Proxy failed', message: err.message }), {
      status: 502, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Access-Control-Allow-Origin': '*' },
    });
  }
}
