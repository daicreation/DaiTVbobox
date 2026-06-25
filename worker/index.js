/**
 * Chill-AI-TV Worker
 * - /, /hk: Hong Kong config
 * - /cn: Mainland config
 * - /{region}/api: aggregated browse/search proxy
 * - /{region}/p/{key}: direct source proxy with adult categories filtered out
 */
const DOMAIN = 'https://daitvbobox.chungshare.workers.dev';

function buildFallback(region = 'hk') {
  const base = `${DOMAIN}/${region}`;
  return {
    sites: [
      { key: 'chill', name: 'Chill-TV', type: 1, api: `${base}/api`, searchable: 1, quickSearch: 1, filterable: 1 },
      { key: 'bfzy', name: 'Storm', type: 1, api: `${base}/p/bfzy`, searchable: 1, quickSearch: 1 },
      { key: 'ff', name: 'FF', type: 1, api: `${base}/p/ff`, searchable: 1, quickSearch: 1 },
      { key: 'sn', name: 'Sony', type: 1, api: `${base}/p/sn`, searchable: 1, quickSearch: 1 },
      { key: 'lz', name: 'LZ', type: 1, api: `${base}/p/lz`, searchable: 1, quickSearch: 1 },
      { key: '360', name: '360', type: 1, api: `${base}/p/360`, searchable: 1, quickSearch: 1 },
      { key: 'js', name: 'JS', type: 1, api: `${base}/p/js`, searchable: 1, quickSearch: 1 },
      { key: 'jy', name: 'JY', type: 1, api: `${base}/p/jy`, searchable: 1, quickSearch: 1 },
      { key: 'wj', name: 'WJ', type: 1, api: `${base}/p/wj`, searchable: 1, quickSearch: 1 },
      { key: 'yh', name: 'YH', type: 1, api: `${base}/p/yh`, searchable: 1, quickSearch: 1 },
      { key: 'md', name: 'MD', type: 1, api: `${base}/p/md`, searchable: 1, quickSearch: 1 },
      { key: 'ik', name: 'iKun', type: 1, api: `${base}/p/ik`, searchable: 1, quickSearch: 1 },
    ],
    flags: ['4K', '1080P', '720P', 'YOUKU', 'iQIYI', 'Tencent', 'Mango'],
    region,
  };
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const route = parseRoute(url.pathname);

    if (route.kind === 'api') {
      return proxyBrowse(url.search);
    }

    if (route.kind === 'proxy') {
      return proxyFiltered(route.proxyKey, url.search);
    }

    try {
      const configFile = route.region === 'cn' ? 'config.cn.json' : 'config.hk.json';
      const apiUrl = `https://api.github.com/repos/daicreation/DaiTVbobox/contents/output/${configFile}`;
      const resp = await fetch(apiUrl, {
        headers: {
          'User-Agent': 'ChillAITV/1.0',
          Accept: 'application/vnd.github.v3+json',
        },
      });

      if (resp.ok) {
        const data = await resp.json();
        const binary = atob(data.content.replace(/\s/g, ''));
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i += 1) {
          bytes[i] = binary.charCodeAt(i);
        }

        const config = JSON.parse(new TextDecoder('utf-8').decode(bytes));
        if (config.sites?.length > 0) {
          config.sites = config.sites.filter((site) => !(site.name || '').includes('采集'));
          return json(config, 200, 'no-cache');
        }
      }
    } catch {}

    return json(buildFallback(route.region), 200, 'no-cache');
  },
};

function parseRoute(pathname) {
  const parts = pathname.split('/').filter(Boolean);
  const first = parts[0] || '';
  const region = first === 'cn' ? 'cn' : 'hk';
  const offset = first === 'hk' || first === 'cn' ? 1 : 0;
  const next = parts[offset] || '';

  if (next === 'api') {
    return { region, kind: 'api', proxyKey: '' };
  }

  if (next === 'p' && parts[offset + 1]) {
    return { region, kind: 'proxy', proxyKey: parts[offset + 1] };
  }

  return { region, kind: 'config', proxyKey: '' };
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
