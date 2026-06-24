/**
 * ============================================================
 * TVBox 影視聚合系統 — Cloudflare Worker (反向代理)
 *
 * 功能:
 *   1. 接收 TVBox APK 的 HTTP 請求
 *   2. 從 GitHub Repo 讀取對應的 JSON / jar 檔案
 *   3. 返回 TVBox 兼容格式的響應
 *   4. 自動緩存 (Cache API)，減輕 GitHub 請求壓力
 *   5. 防盜連 (可選)
 *   6. CORS 支援
 *
 * 部署步驟:
 *   1. 複製此檔案到 Cloudflare Workers 面板
 *   2. 修改 GITHUB_REPO_OWNER 和 GITHUB_REPO_NAME
 *   3. 修改 WORKER_DOMAIN 為你的域名
 *   4. 綁定自訂域名 (如 tv.yourname.com)
 *   5. 如需清除快取: 訪問 https://tv.xxx.com/purge
 *
 * 路由設計:
 *   /              → config.json   (TVBox 主配置)
 *   /api           → config.json   (聚合搜尋 API)
 *   /movie         → movie.json    (電影列表)
 *   /tv            → tv.json       (電視劇列表)
 *   /variety       → variety.json  (綜藝列表)
 *   /live          → live.json     (直播列表)
 *   /spider.jar    → spider.jar    (爬蟲規則包)
 *   /health        → "OK"          (健康檢查)
 *   /purge         → 清除快取      (管理用)
 *
 * ============================================================
 */

// ============================================================
// 【設定區域】— 部署前請修改以下變數
// ============================================================

// GitHub Repo 資訊
// 格式: https://raw.githubusercontent.com/{owner}/{repo}/main/output/
const GITHUB_OWNER = 'daicreation';                  // GitHub 使用者名稱
const GITHUB_REPO = 'DaiTVbobox';                   // Repo 名稱
const GITHUB_BRANCH = 'main';                        // 分支名稱
const GITHUB_RAW_BASE = `https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/${GITHUB_BRANCH}`;

// Worker 網域 (用於 config.json 中的 api URL)
const WORKER_DOMAIN = 'https://tv.xxx.com';          // 修改為你的域名

// 快取時間 (秒)
const CACHE_TTL = {
  json: 3600,        // JSON 檔案: 1 小時
  jar: 86400,        // spider.jar: 24 小時
  default: 3600,
};

// 防盜連設定
const ANTI_LEECH = {
  enabled: false,                          // 是否啟用防盜連
  allowedReferers: [],                     // 允許的 Referer (空 = 不檢查)
  allowedUserAgents: [
    'TVBox', 'okhttp', 'Dalvik', 'Apache-HttpClient',
    'Mozilla', 'Chrome', 'curl',           // 寬鬆模式，允許大部分客戶端
  ],
};

// 速率限制
const RATE_LIMIT = {
  enabled: true,
  maxRequestsPerMinute: 60,                // 每 IP 每分鐘最大請求數
};


// ============================================================
// 【路由映射】— 請求路徑 → GitHub 檔案路徑
// ============================================================
const ROUTE_MAP = {
  '/':              { file: 'output/config.json',   type: 'json' },
  '/api':           { file: 'output/config.json',   type: 'json' },
  '/movie':         { file: 'output/movie.json',    type: 'json' },
  '/tv':            { file: 'output/tv.json',       type: 'json' },
  '/variety':       { file: 'output/variety.json',  type: 'json' },
  '/live':          { file: 'output/live.json',     type: 'json' },
  '/config.json':   { file: 'output/config.json',   type: 'json' },
  '/spider.jar':    { file: 'spider/spider.jar',    type: 'jar' },
};

// Content-Type 對照表
const CONTENT_TYPES = {
  json: 'application/json; charset=utf-8',
  jar: 'application/java-archive',
  html: 'text/html; charset=utf-8',
  text: 'text/plain; charset=utf-8',
};


// ============================================================
// 【主處理函數】— Cloudflare Worker 入口
// ============================================================
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const clientIP = request.headers.get('CF-Connecting-IP') || 'unknown';

    // ---- 速率限制檢查 ----
    if (RATE_LIMIT.enabled) {
      const rateLimitKey = `rate_${clientIP}`;
      // 使用 Cache API 做簡易速率限制
      const cache = caches.default;
      let rateCache = await cache.match(rateLimitKey);
      let count = 0;

      if (rateCache) {
        count = parseInt(await rateCache.text()) || 0;
        if (count >= RATE_LIMIT.maxRequestsPerMinute) {
          return new Response('請求過於頻繁，請稍後再試 (Rate Limited)', {
            status: 429,
            headers: { 'Retry-After': '60' },
          });
        }
      }

      count++;
      // 建立速率限制快取 (1分鐘過期)
      rateCache = new Response(count.toString(), {
        headers: { 'Cache-Control': 'public, max-age=60' },
      });
      ctx.waitUntil(cache.put(rateLimitKey, rateCache));
    }

    // ---- 特殊路由處理 ----
    // 健康檢查
    if (path === '/health') {
      return new Response('OK', {
        status: 200,
        headers: { 'Content-Type': CONTENT_TYPES.text },
      });
    }

    // 清除快取 (管理功能)
    if (path === '/purge') {
      return handlePurge(request, env, ctx);
    }

    // 首頁說明
    if (path === '/about' || path === '/info') {
      return handleInfo();
    }

    // ---- 主要路由處理 ----
    const route = ROUTE_MAP[path];
    if (!route) {
      // 返回 404 + 使用說明
      return new Response(
        JSON.stringify({
          error: 'Not Found',
          message: '此路徑不存在。可用路徑: / /movie /tv /variety /live /spider.jar /health',
          docs: `${WORKER_DOMAIN}/about`,
        }, null, 2),
        {
          status: 404,
          headers: {
            'Content-Type': CONTENT_TYPES.json,
            'Access-Control-Allow-Origin': '*',
          },
        }
      );
    }

    // ---- 防盜連檢查 ----
    if (ANTI_LEECH.enabled) {
      const check = checkAntiLeech(request);
      if (!check.allowed) {
        return new Response('Forbidden', { status: 403 });
      }
    }

    // ---- 獲取內容 (含快取) ----
    const githubURL = `${GITHUB_RAW_BASE}/${route.file}`;
    const cacheKey = new Request(githubURL, { method: 'GET' });

    // 嘗試從快取獲取
    const cache = caches.default;
    let response = await cache.match(cacheKey);

    if (!response) {
      // 快取未命中，從 GitHub 獲取
      try {
        response = await fetch(githubURL, {
          headers: {
            'User-Agent': 'TVBox-Aggregator/1.0 (Cloudflare Worker)',
            'Accept': 'application/json, */*',
          },
        });

        if (!response.ok) {
          console.error(`GitHub 回應錯誤: ${response.status} ${githubURL}`);
          return new Response(
            JSON.stringify({
              error: '上游獲取失敗',
              status: response.status,
              message: 'GitHub Repo 暫時無法訪問，請稍後再試',
            }),
            {
              status: 502,
              headers: {
                'Content-Type': CONTENT_TYPES.json,
                'Access-Control-Allow-Origin': '*',
              },
            }
          );
        }

        // 複製回應並設定快取控制
        const ttl = CACHE_TTL[route.type] || CACHE_TTL.default;
        response = new Response(response.body, response);
        response.headers.set('Cache-Control', `public, max-age=${ttl}, s-maxage=${ttl}`);
        response.headers.set('X-Cache', 'MISS');
        response.headers.set('X-Source', 'GitHub');

        // 異步存入快取
        ctx.waitUntil(cache.put(cacheKey, response.clone()));

      } catch (err) {
        console.error(`獲取失敗: ${err.message}`);

        // 嘗試返回過期快取 (stale-while-revalidate)
        const staleResponse = await cache.match(cacheKey, { ignoreMethod: true });
        if (staleResponse) {
          staleResponse.headers.set('X-Cache', 'STALE');
          return staleResponse;
        }

        return new Response(
          JSON.stringify({
            error: '服務暫時不可用',
            message: '無法連接到上游，且無可用快取',
          }),
          {
            status: 503,
            headers: {
              'Content-Type': CONTENT_TYPES.json,
              'Access-Control-Allow-Origin': '*',
            },
          }
        );
      }
    } else {
      response = new Response(response.body, response);
      response.headers.set('X-Cache', 'HIT');
    }

    // ---- 設定通用回應頭 ----
    const headers = new Headers(response.headers);
    headers.set('Access-Control-Allow-Origin', '*');
    headers.set('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS');
    headers.set('Access-Control-Allow-Headers', 'Content-Type, User-Agent');
    headers.set('X-Proxy-By', 'Cloudflare Worker');
    headers.set('X-Powered-By', 'TVBox-Aggregator/1.0');

    // 確保正確的 Content-Type
    if (!headers.has('Content-Type') || headers.get('Content-Type').includes('text/plain')) {
      headers.set('Content-Type', CONTENT_TYPES[route.type] || CONTENT_TYPES.default);
    }

    return new Response(response.body, {
      status: response.status,
      headers: headers,
    });
  },
};


// ============================================================
// 【輔助函數】
// ============================================================

/**
 * 防盜連檢查
 *
 * 檢查請求的 Referer 和 User-Agent 是否符合白名單
 * TVBox 客戶端通常帶有特定的 User-Agent
 *
 * @param {Request} request - HTTP 請求
 * @returns {{allowed: boolean, reason: string}}
 */
function checkAntiLeech(request) {
  const referer = request.headers.get('Referer') || '';
  const userAgent = request.headers.get('User-Agent') || '';

  // 如果沒有設定允許的 Referer，跳過 Referer 檢查
  if (ANTI_LEECH.allowedReferers.length > 0) {
    const refererAllowed = ANTI_LEECH.allowedReferers.some(r =>
      referer.toLowerCase().includes(r.toLowerCase())
    );
    if (!refererAllowed && referer !== '') {
      // 直接訪問 (無 Referer) 通常是 TVBox，允許
      return { allowed: true, reason: 'no-referer' };
    }
  }

  // 檢查 User-Agent (寬鬆模式: 包含任何一個關鍵字即放行)
  if (ANTI_LEECH.allowedUserAgents.length > 0) {
    const uaAllowed = ANTI_LEECH.allowedUserAgents.some(ua =>
      userAgent.includes(ua)
    );
    if (!uaAllowed) {
      return { allowed: false, reason: `User-Agent blocked: ${userAgent.substring(0, 100)}` };
    }
  }

  return { allowed: true, reason: 'ok' };
}


/**
 * 處理 CORS 預檢請求 (OPTIONS)
 *
 * Cloudflare Worker 會自動處理，但此函數提供更精細的控制
 */
function handleOptions(request) {
  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, User-Agent',
      'Access-Control-Max-Age': '86400',
    },
  });
}


/**
 * 清除所有快取
 *
 * 在發布新 JSON 後，訪問 https://tv.xxx.com/purge 來清除快取
 * 建議設定一個只有你知道的 Token 來保護此功能
 *
 * @param {Request} request - HTTP 請求
 * @param {object} env - 環境變數 (可在此設定 PURGE_TOKEN)
 * @param {object} ctx - 執行上下文
 */
async function handlePurge(request, env, ctx) {
  // 簡易 Token 保護 (可選)
  const url = new URL(request.url);
  const token = url.searchParams.get('token');
  const expectedToken = env.PURGE_TOKEN || 'admin123';  // 修改此 Token

  if (token !== expectedToken) {
    return new Response(
      JSON.stringify({ error: 'Invalid or missing purge token' }),
      {
        status: 401,
        headers: { 'Content-Type': CONTENT_TYPES.json },
      }
    );
  }

  const cache = caches.default;
  // 清除所有相關快取 (Cache API 沒有 "clear all" 方法，需要逐一刪除)
  const keys = await caches.default.keys();
  let deleted = 0;

  for (const key of keys) {
    if (key.url.includes(GITHUB_RAW_BASE)) {
      await cache.delete(key);
      deleted++;
    }
  }

  return new Response(
    JSON.stringify({
      success: true,
      message: `已清除 ${deleted} 個快取項目`,
      timestamp: new Date().toISOString(),
    }),
    {
      status: 200,
      headers: { 'Content-Type': CONTENT_TYPES.json },
    }
  );
}


/**
 * 顯示系統資訊
 *
 * 訪問 https://tv.xxx.com/about 查看
 */
function handleInfo() {
  const info = {
    name: 'TVBox 影視聚合系統',
    version: '1.0.0',
    powered_by: 'Cloudflare Worker',
    domain: WORKER_DOMAIN,
    github_repo: `${GITHUB_OWNER}/${GITHUB_REPO}`,
    endpoints: {
      config: `${WORKER_DOMAIN}/`,
      movie: `${WORKER_DOMAIN}/movie`,
      tv: `${WORKER_DOMAIN}/tv`,
      variety: `${WORKER_DOMAIN}/variety`,
      live: `${WORKER_DOMAIN}/live`,
      spider: `${WORKER_DOMAIN}/spider.jar`,
      health: `${WORKER_DOMAIN}/health`,
    },
    features: [
      '多源聚合 (飯太硬/肥貓/OK/小蘋果/4K專用倉)',
      '自動評分排序 (速度+成功率+穩定性+畫質)',
      '4K 優先',
      '愛奇藝/騰訊/優酷/芒果 平台分類',
      '每日自動更新 (GitHub Actions)',
      'Cloudflare CDN 全球加速',
      '防盜連 & 速率限制',
    ],
    cache_ttl: CACHE_TTL,
    update_time: new Date().toISOString(),
  };

  return new Response(JSON.stringify(info, null, 2), {
    status: 200,
    headers: {
      'Content-Type': CONTENT_TYPES.json,
      'Access-Control-Allow-Origin': '*',
    },
  });
}
