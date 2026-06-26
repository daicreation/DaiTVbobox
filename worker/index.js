/**
 * Chill-AI-TV Worker
 * - /, /hk, /cn: shared config
 * - /api, /hk/api, /cn/api: homepage/detail proxy split
 * - /p/{key}, /hk/p/{key}, /cn/p/{key}: direct source proxy
 */
const DOMAIN = 'https://chilltv.chungchung.online';
const GITHUB_OUTPUT_API_BASE = 'https://api.github.com/repos/daicreation/DaiTVbobox/contents/output';
const GITHUB_FETCH_TIMEOUT_MS = 3000;
const HOT_TV_CLASS = { type_id: 'hot_tv', type_name: '電視劇' };
const DOUBAN_REFERER = 'https://m.douban.com/subject_collection/tv_domestic';
const SITE_NAME_BLOCKLIST = ['采集', '理論', '理论', '福利', '成人', '直播', '短剧', '短劇', '云盘', '雲盤', '网盘', '網盤', 'alist', '配置'];
const SITE_URL_BLOCKLIST = ['.js', '.py', 'drpy', 'spider', 'get.js', '/lib/', 'live?url=', 'csp_', '/vod/json', 'json?url='];

function buildFallback() {
  const base = DOMAIN;
  return {
    sites: [
      { key: 'chill', name: '🧊 Chill-TV', type: 1, api: `${base}/api`, searchable: 1, quickSearch: 1, filterable: 1 },
      { key: 'bfzy', name: '🔥 暴風', type: 1, api: `${base}/p/bfzy`, searchable: 1, quickSearch: 1 },
      { key: 'ff', name: '⚡ 非凡', type: 1, api: `${base}/p/ff`, searchable: 1, quickSearch: 1 },
      { key: 'sn', name: '🎯 索尼', type: 1, api: `${base}/p/sn`, searchable: 1, quickSearch: 1 },
      { key: 'lz', name: '🔮 量子', type: 1, api: `${base}/p/lz`, searchable: 1, quickSearch: 1 },
      { key: '360', name: '💠 360', type: 1, api: `${base}/p/360`, searchable: 1, quickSearch: 1 },
      { key: 'js', name: '⚡ 極速', type: 1, api: `${base}/p/js`, searchable: 1, quickSearch: 1 },
      { key: 'jy', name: '🦅 金鷹', type: 1, api: `${base}/p/jy`, searchable: 1, quickSearch: 1 },
      { key: 'yh', name: '🌸 櫻花', type: 1, api: `${base}/p/yh`, searchable: 1, quickSearch: 1 },
      { key: 'md', name: '🏙️ 魔都', type: 1, api: `${base}/p/md`, searchable: 1, quickSearch: 1 },
      { key: 'ik', name: 'iKun', type: 1, api: `${base}/p/ik`, searchable: 1, quickSearch: 1 },
      { key: 'wj', name: '♾️ 無盡', type: 1, api: `${base}/p/wj`, searchable: 1, quickSearch: 1 },
    ],
    region: 'shared',
  };
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const route = parseRoute(url.pathname);

    if (route.kind === 'api') {
      if (isHotTvDetail(url)) {
        const detailResponse = await serveHotTvDetail(url);
        if (detailResponse) {
          return detailResponse;
        }
      }

      if (isHomepageLike(url) || isHotTvCategory(url)) {
        const homepageResponse = await serveHotTvHomepage();
        if (homepageResponse) {
          return homepageResponse;
        }
      }

      return proxyBrowse(url.search);
    }

    if (route.kind === 'proxy') {
      return proxyFiltered(route.proxyKey, url.search);
    }

    if (route.kind === 'image') {
      return proxyImageAsset(url);
    }

    const config = await fetchRepoOutputJson('config.json');
    if (config?.sites?.length > 0) {
      config.sites = config.sites.filter(isAllowedSite);
      return json(config, 200, 'no-cache');
    }

    return json(buildFallback(), 200, 'no-cache');
  },
};

function parseRoute(pathname) {
  const parts = pathname.split('/').filter(Boolean);
  const first = parts[0] || '';
  const offset = first === 'hk' || first === 'cn' ? 1 : 0;
  const next = parts[offset] || '';

  if (next === 'api') {
    return { kind: 'api', proxyKey: '' };
  }

  if (next === 'p' && parts[offset + 1]) {
    return { kind: 'proxy', proxyKey: parts[offset + 1] };
  }

  if (next === 'img') {
    return { kind: 'image', proxyKey: '' };
  }

  return { kind: 'config', proxyKey: '' };
}

const PROXY_MAP = {
  bfzy: 'https://bfzyapi.com/api.php/provide/vod',
  ff: 'http://cj.ffzyapi.com/api.php/provide/vod',
  sn: 'https://suoniapi.com/api.php/provide/vod',
  lz: 'https://cj.lziapi.com/api.php/provide/vod/',
  360: 'https://360zyzz.com/api.php/provide/vod/',
  js: 'https://jszyapi.com/api.php/provide/vod/',
  jy: 'https://jyzyapi.com/provide/vod/',
  wj: 'https://api.wujinapi.me/api.php/provide/vod',
  yh: 'https://m3u8.apiyhzy.com/api.php/provide/vod',
  md: 'https://www.mdzyapi.com/api.php/provide/vod',
  ik: 'https://ikunzyapi.com/api.php/provide/vod',
};

async function proxyFiltered(key, search) {
  const target = PROXY_MAP[key];
  if (!target) {
    return json({ code: 0, list: [], class: [] });
  }
  return proxyBrowse(search, target);
}

function isHomepageLike(url) {
  const params = url.searchParams;
  const ac = (params.get('ac') || '').toLowerCase();
  if (ac === 'list') {
    return isHomepageListRequest(params);
  }
  if (ac) {
    return false;
  }

  const keys = [...params.keys()];
  if (keys.length === 0) {
    return true;
  }
  if (params.has('wd') || params.has('ids')) {
    return false;
  }

  return keys.every((key) => key === 'pg' || key === 'page' || key === 'limit');
}

function isHomepageListRequest(params) {
  const keys = [...params.keys()];
  if (params.has('wd') || params.has('ids')) {
    return false;
  }
  return keys.every((key) => key === 'ac' || key === 'pg' || key === 'page' || key === 'limit');
}

function isHotTvDetail(url) {
  return (url.searchParams.get('ac') || '').toLowerCase() === 'detail' && Boolean(getRequestedVodId(url));
}

function isHotTvCategory(url) {
  const params = url.searchParams;
  const typeId = (params.get('t') || '').trim().toLowerCase();
  if (typeId !== HOT_TV_CLASS.type_id) {
    return false;
  }

  if (params.has('wd') || params.has('ids')) {
    return false;
  }

  const ac = (params.get('ac') || '').toLowerCase();
  return ac === '' || ac === 'list' || ac === 'videolist';
}

function getRequestedVodId(url) {
  return (url.searchParams.get('ids') || '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean)[0] || '';
}

async function serveHotTvHomepage() {
  const hotTv = await fetchRepoOutputJson('hot_tv.json');
  if (!hotTv || !Array.isArray(hotTv.list)) {
    return null;
  }
  const normalized = normalizeHotTvPayload(hotTv);

  return json({
    code: 1,
    msg: '',
    page: 1,
    pagecount: 1,
    limit: normalized.list.length,
    total: normalized.list.length,
    class: [],
    list: normalized.list,
    update_time: normalized.update_time || '',
  }, 200, 'no-cache');
}

async function serveHotTvDetail(url) {
  const hotTv = await fetchRepoOutputJson('hot_tv.json');
  const normalized = normalizeHotTvPayload(hotTv);
  const vodId = getRequestedVodId(url);
  let detail = normalized?.details?.[vodId];
  if (!detail) {
    const homepageItem = (normalized?.list || []).find((item) => item?.vod_id === vodId);
    if (homepageItem?.vod_name) {
      detail = await resolveHotTvDetailByTitle(homepageItem.vod_name, homepageItem.vod_remarks || '');
      if (detail) {
        detail = normalizeHotTvItem(detail);
      }
    }
  }
  if (!detail) {
    return null;
  }

  return json({
    code: 1,
    msg: '',
    list: [detail],
    update_time: normalized.update_time || '',
  }, 200, 'no-cache');
}

async function resolveHotTvDetailByTitle(title, remarks = '') {
  const query = String(title || '').trim();
  if (!query) {
    return null;
  }

  for (const [sourceKey, target] of Object.entries(PROXY_MAP)) {
    const searchData = await fetchSourceJson(target, { wd: query });
    const candidate = pickSourceListItem(searchData, query);
    if (!candidate) {
      continue;
    }

    const vodId = String(candidate.vod_id || candidate.id || '').trim();
    if (!vodId) {
      continue;
    }

    const detailData = await fetchSourceJson(target, { ac: 'detail', ids: vodId });
    const detail = pickSourceDetailItem(detailData, vodId);
    if (!detail) {
      continue;
    }

    detail._source_name = sourceKey;
    if (!detail.vod_name) {
      detail.vod_name = query;
    }
    if (!detail.vod_remarks && remarks) {
      detail.vod_remarks = remarks;
    }
    return detail;
  }

  return null;
}

async function fetchSourceJson(target, params) {
  const api = target || 'https://bfzyapi.com/api.php/provide/vod';
  try {
    const query = new URLSearchParams(params || {}).toString();
    const response = await fetch(query ? `${api}?${query}` : api, {
      method: 'GET',
      headers: { 'User-Agent': 'ChillAITV/1.0' },
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) {
      return null;
    }
    return await response.json();
  } catch {
    return null;
  }
}

function pickSourceListItem(payload, title) {
  const items = Array.isArray(payload?.list) ? payload.list : [];
  if (items.length === 0) {
    return null;
  }

  const normalizedTitle = String(title || '').trim().toLowerCase();
  for (const item of items) {
    const itemTitle = String(item?.vod_name || item?.vod_en || '').trim().toLowerCase();
    if (itemTitle && (itemTitle === normalizedTitle || itemTitle.includes(normalizedTitle) || normalizedTitle.includes(itemTitle))) {
      return item;
    }
  }

  return items[0] || null;
}

function pickSourceDetailItem(payload, vodId) {
  const items = Array.isArray(payload?.list) ? payload.list : [];
  if (items.length === 0) {
    return null;
  }

  const normalizedVodId = String(vodId || '').trim();
  for (const item of items) {
    const itemVodId = String(item?.vod_id || item?.id || '').trim();
    if (itemVodId && itemVodId === normalizedVodId) {
      return item;
    }
    if (String(item?.vod_play_url || '').trim()) {
      return item;
    }
  }

  return null;
}

function normalizeHotTvPayload(hotTv) {
  if (!hotTv || !Array.isArray(hotTv.list)) {
    return hotTv;
  }

  const list = hotTv.list.map((item) => normalizeHotTvItem(item));
  const details = Object.fromEntries(
    Object.entries(hotTv.details || {}).map(([vodId, detail]) => [vodId, normalizeHotTvItem(detail)])
  );

  return {
    ...hotTv,
    list,
    details,
  };
}

function normalizeHotTvItem(item) {
  if (!item || typeof item !== 'object') {
    return item;
  }

  return {
    ...item,
    vod_pic: normalizePosterUrl(item.vod_pic),
  };
}

function normalizePosterUrl(value) {
  const raw = String(value || '').trim();
  if (!/^https?:\/\//i.test(raw)) {
    return raw;
  }

  try {
    const parsed = new URL(raw);
    let target = raw;
    if (parsed.pathname === '/img') {
      target = (parsed.searchParams.get('url') || '').trim() || raw;
    }
    return `${DOMAIN}/img?url=${encodeURIComponent(target)}`;
  } catch {
    return raw;
  }
}

async function proxyImageAsset(url) {
  const target = (url.searchParams.get('url') || '').trim();
  if (!/^https?:\/\//i.test(target)) {
    return new Response('Bad Request', { status: 400 });
  }

  try {
    const response = await fetch(target, {
      headers: {
        'User-Agent': 'Mozilla/5.0',
        Referer: target.includes('doubanio.com') ? DOUBAN_REFERER : DOMAIN,
        Accept: 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
      },
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) {
      return new Response('Upstream image fetch failed', { status: response.status || 502 });
    }

    const headers = new Headers();
    const contentType = response.headers.get('Content-Type');
    if (contentType) {
      headers.set('Content-Type', contentType);
    }
    headers.set('Cache-Control', 'public, max-age=86400');
    return new Response(response.body, {
      status: response.status,
      headers,
    });
  } catch {
    return new Response('Upstream image fetch failed', { status: 502 });
  }
}

async function fetchRepoOutputJson(filename) {
  const timeout = createTimeoutSignal(GITHUB_FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(`${GITHUB_OUTPUT_API_BASE}/${filename}`, {
      headers: {
        'User-Agent': 'ChillAITV/1.0',
        Accept: 'application/vnd.github.v3+json',
      },
      signal: timeout.signal,
    });
    if (!response.ok) {
      return null;
    }

    const payload = await response.json();
    const binary = atob((payload.content || '').replace(/\s/g, ''));
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return JSON.parse(new TextDecoder('utf-8').decode(bytes));
  } catch {
    return null;
  } finally {
    timeout.cleanup();
  }
}

function createTimeoutSignal(timeoutMs) {
  if (typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function') {
    return {
      signal: AbortSignal.timeout(timeoutMs),
      cleanup() {},
    };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  return {
    signal: controller.signal,
    cleanup() {
      clearTimeout(timeoutId);
    },
  };
}

async function proxyBrowse(search = '', target) {
  const api = target || 'https://bfzyapi.com/api.php/provide/vod';
  try {
    const response = await fetch(api + search, {
      headers: { 'User-Agent': 'ChillAITV/1.0' },
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) {
      return json({ code: 0, list: [], class: [] });
    }

    const data = await response.json();
    const blockedTypeIds = [29, 73];
    if (data.list) {
      data.list = data.list.filter((item) => !blockedTypeIds.includes(item.type_id));
    }
    if (data.class) {
      data.class = data.class.filter((item) => !blockedTypeIds.includes(item.type_id));
    }
    return json(data);
  } catch {
    return json({ code: 0, list: [], class: [] });
  }
}

function json(data, status = 200, cacheControl = 'public, max-age=300') {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': cacheControl,
    },
  });
}

function isAllowedSite(site) {
  const name = String(site?.name || '').toLowerCase();
  const api = String(site?.api || '').toLowerCase();
  if (!api.startsWith('http')) {
    return false;
  }
  if (SITE_NAME_BLOCKLIST.some((keyword) => name.includes(keyword.toLowerCase()))) {
    return false;
  }
  if (SITE_URL_BLOCKLIST.some((keyword) => api.includes(keyword))) {
    return false;
  }
  return true;
}
