import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { Buffer } from 'node:buffer';

const workerModulePromise = loadWorkerModule();
const GITHUB_HOT_TV_URL = 'https://api.github.com/repos/daicreation/DaiTVbobox/contents/output/hot_tv.json';
const GITHUB_CONFIG_URL = 'https://api.github.com/repos/daicreation/DaiTVbobox/contents/output/config.json';
const DEFAULT_PROXY_URL = 'https://bfzyapi.com/api.php/provide/vod';
const CURRENT_WORKER_DOMAIN = 'https://chilltv.chungchung.online';
const STALE_PROXY_POSTER = 'https://tv.example.com/img?url=https%3A%2F%2Fimg.example.com%2Fhot-show.jpg';
const HOT_TV_CLASS = { type_id: 'hot_tv', type_name: '電視劇' };

const HOT_TV_FIXTURE = {
  update_time: '2026-06-26 00:00:00',
  list: [
    {
      vod_id: 'tv_hot_1',
      vod_name: 'Hot Show',
      vod_pic: STALE_PROXY_POSTER,
      vod_remarks: 'Updated to episode 8',
      source_count: 1,
    },
  ],
  details: {
    tv_hot_1: {
      vod_id: 'tv_hot_1',
      vod_name: 'Hot Show',
      vod_pic: STALE_PROXY_POSTER,
      vod_remarks: 'Updated to episode 8',
      type_name: 'TV',
      source_count: 1,
      vod_play_from: 'storm$1080P',
      vod_play_url: 'Episode 1$https://play.example.com/hot-show.m3u8',
    },
  },
};

async function loadWorkerModule() {
  const source = await readFile(new URL('../worker/index.js', import.meta.url), 'utf8');
  const encoded = Buffer.from(source, 'utf8').toString('base64');
  return import(`data:text/javascript;base64,${encoded}`);
}

function encodeGitHubContent(payload) {
  return Buffer.from(JSON.stringify(payload), 'utf8').toString('base64');
}

async function runWithFetchStub(handler, callback) {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input.url;
    calls.push({ url, init });
    return handler(url, init);
  };

  try {
    return await callback(calls);
  } finally {
    globalThis.fetch = originalFetch;
  }
}

function makeJsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}

function makeGitHubFileResponse(payload, status = 200) {
  return makeJsonResponse({ content: encodeGitHubContent(payload) }, status);
}

function makeAbortError(message = 'aborted') {
  const error = new Error(message);
  error.name = 'AbortError';
  return error;
}

test('homepage-like api routes read hot_tv.json before proxying', async () => {
  const worker = (await workerModulePromise).default;

  await runWithFetchStub((url) => {
    if (url === GITHUB_HOT_TV_URL) {
      return makeGitHubFileResponse(HOT_TV_FIXTURE);
    }
    if (url.startsWith(DEFAULT_PROXY_URL)) {
      return makeJsonResponse({ code: 1, list: [{ vod_id: 'proxy_only' }], class: [] });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const response = await worker.fetch(new Request('https://worker.example/hk/api'));
    const payload = await response.json();

    assert.equal(payload.list[0].vod_pic, `${CURRENT_WORKER_DOMAIN}/img?url=https%3A%2F%2Fimg.example.com%2Fhot-show.jpg`);
    assert.deepEqual(payload.class, []);
    assert.equal(calls.filter((call) => call.url === GITHUB_HOT_TV_URL).length, 1);
    assert.equal(calls.some((call) => call.url.startsWith(DEFAULT_PROXY_URL)), false);
  });
});

test('hot_tv category requests read hot_tv.json before proxying', async () => {
  const worker = (await workerModulePromise).default;

  await runWithFetchStub((url) => {
    if (url === GITHUB_HOT_TV_URL) {
      return makeGitHubFileResponse(HOT_TV_FIXTURE);
    }
    if (url.startsWith(DEFAULT_PROXY_URL)) {
      return makeJsonResponse({ code: 1, list: [{ vod_id: 'proxy_only' }], class: [] });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const response = await worker.fetch(new Request('https://worker.example/api?ac=list&t=hot_tv&pg=1'));
    const payload = await response.json();

    assert.equal(payload.list[0].vod_pic, `${CURRENT_WORKER_DOMAIN}/img?url=https%3A%2F%2Fimg.example.com%2Fhot-show.jpg`);
    assert.equal(calls.filter((call) => call.url === GITHUB_HOT_TV_URL).length, 1);
    assert.equal(calls.some((call) => call.url.startsWith(DEFAULT_PROXY_URL)), false);
  });
});

test('hot_tv category requests without ac=list still read hot_tv.json before proxying', async () => {
  const worker = (await workerModulePromise).default;

  await runWithFetchStub((url) => {
    if (url === GITHUB_HOT_TV_URL) {
      return makeGitHubFileResponse(HOT_TV_FIXTURE);
    }
    if (url.startsWith(DEFAULT_PROXY_URL)) {
      return makeJsonResponse({ code: 1, list: [{ vod_id: 'proxy_only' }], class: [] });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const response = await worker.fetch(new Request('https://worker.example/api?t=hot_tv&pg=1'));
    const payload = await response.json();

    assert.equal(payload.list[0].vod_pic, `${CURRENT_WORKER_DOMAIN}/img?url=https%3A%2F%2Fimg.example.com%2Fhot-show.jpg`);
    assert.equal(calls.filter((call) => call.url === GITHUB_HOT_TV_URL).length, 1);
    assert.equal(calls.some((call) => call.url.startsWith(DEFAULT_PROXY_URL)), false);
  });
});

test('hot_tv category requests remain supported for videolist route', async () => {
  const worker = (await workerModulePromise).default;

  await runWithFetchStub((url) => {
    if (url === GITHUB_HOT_TV_URL) {
      return makeGitHubFileResponse(HOT_TV_FIXTURE);
    }
    if (url.startsWith(DEFAULT_PROXY_URL)) {
      return makeJsonResponse({ code: 1, list: [{ vod_id: 'proxy_only' }], class: [] });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const response = await worker.fetch(new Request('https://worker.example/api?ac=videolist&t=hot_tv&pg=1'));
    const payload = await response.json();

    assert.equal(payload.list[0].vod_pic, `${CURRENT_WORKER_DOMAIN}/img?url=https%3A%2F%2Fimg.example.com%2Fhot-show.jpg`);
    assert.equal(calls.filter((call) => call.url === GITHUB_HOT_TV_URL).length, 1);
    assert.equal(calls.some((call) => call.url.startsWith(DEFAULT_PROXY_URL)), false);
  });
});

test('detail api routes return prebuilt hot_tv detail when the vod_id is matched', async () => {
  const worker = (await workerModulePromise).default;

  await runWithFetchStub((url) => {
    if (url === GITHUB_HOT_TV_URL) {
      return makeGitHubFileResponse(HOT_TV_FIXTURE);
    }
    if (url.startsWith(DEFAULT_PROXY_URL)) {
      return makeJsonResponse({ code: 1, list: [{ vod_id: 'proxy_only' }], class: [] });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const response = await worker.fetch(new Request('https://worker.example/cn/api?ac=detail&ids=tv_hot_1'));
    const payload = await response.json();

    assert.equal(payload.list[0].vod_pic, `${CURRENT_WORKER_DOMAIN}/img?url=https%3A%2F%2Fimg.example.com%2Fhot-show.jpg`);
    assert.equal(calls.filter((call) => call.url === GITHUB_HOT_TV_URL).length, 1);
    assert.equal(calls.some((call) => call.url.startsWith(DEFAULT_PROXY_URL)), false);
  });
});

test('detail api routes fall back to source lookup when hot_tv detail is missing', async () => {
  const worker = (await workerModulePromise).default;
  const hotTvWithoutDetail = {
    ...HOT_TV_FIXTURE,
    list: [
      {
        vod_id: 'tv_hot_missing_detail',
        vod_name: 'Fallback Show',
        vod_pic: STALE_PROXY_POSTER,
        vod_remarks: 'Douban rank',
        source_count: 0,
      },
    ],
    details: {},
  };

  await runWithFetchStub((url) => {
    if (url === GITHUB_HOT_TV_URL) {
      return makeGitHubFileResponse(hotTvWithoutDetail);
    }
    if (url === `${DEFAULT_PROXY_URL}?wd=Fallback+Show`) {
      return makeJsonResponse({
        list: [
          { vod_id: 'bfzy-1', vod_name: 'Fallback Show' },
        ],
      });
    }
    if (url === `${DEFAULT_PROXY_URL}?ac=detail&ids=bfzy-1`) {
      return makeJsonResponse({
        list: [
          {
            vod_id: 'bfzy-1',
            vod_name: 'Fallback Show',
            vod_pic: 'https://img.example.com/fallback-show.jpg',
            vod_play_from: 'bfzy',
            vod_play_url: 'Episode 1$https://play.example.com/fallback-show.m3u8',
          },
        ],
      });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const response = await worker.fetch(new Request('https://worker.example/api?ac=detail&ids=tv_hot_missing_detail'));
    const payload = await response.json();

    assert.equal(payload.list[0].vod_name, 'Fallback Show');
    assert.equal(payload.list[0].vod_pic, `${CURRENT_WORKER_DOMAIN}/img?url=https%3A%2F%2Fimg.example.com%2Ffallback-show.jpg`);
    assert.equal(payload.list[0].vod_play_from, 'bfzy');
    assert.equal(payload.list[0].vod_play_url, 'Episode 1$https://play.example.com/fallback-show.m3u8');
    assert.equal(payload.list[0].source_count, 1);
    assert.equal(calls.filter((call) => call.url === GITHUB_HOT_TV_URL).length, 1);
    assert.equal(calls.filter((call) => call.url.includes('Fallback+Show')).length >= 1, true);
  });
});

test('non-hot detail and search api routes still proxy to the upstream source', async () => {
  const worker = (await workerModulePromise).default;

  await runWithFetchStub((url) => {
    if (url === GITHUB_HOT_TV_URL) {
      return makeGitHubFileResponse(HOT_TV_FIXTURE);
    }
    if (url === `${DEFAULT_PROXY_URL}?ac=detail&ids=missing_id`) {
      return makeJsonResponse({ code: 1, list: [{ vod_id: 'missing_id', from: 'proxy' }], class: [] });
    }
    if (url === `${DEFAULT_PROXY_URL}?wd=keyword`) {
      return makeJsonResponse({ code: 1, list: [{ vod_id: 'search_result', from: 'proxy' }], class: [] });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const detailResponse = await worker.fetch(new Request('https://worker.example/api?ac=detail&ids=missing_id'));
    const detailPayload = await detailResponse.json();
    assert.deepEqual(detailPayload.list, [{ vod_id: 'missing_id', from: 'proxy' }]);

    const searchResponse = await worker.fetch(new Request('https://worker.example/api?wd=keyword'));
    const searchPayload = await searchResponse.json();
    assert.deepEqual(searchPayload.list, [{ vod_id: 'search_result', from: 'proxy' }]);

    assert.equal(calls.filter((call) => call.url === GITHUB_HOT_TV_URL).length, 1);
    assert.equal(calls.filter((call) => call.url.startsWith(`${DEFAULT_PROXY_URL}?`)).length, 2);
  });
});

test('ac=list with extra filters stays on proxy instead of hot_tv homepage', async () => {
  const worker = (await workerModulePromise).default;

  await runWithFetchStub((url) => {
    if (url === `${DEFAULT_PROXY_URL}?ac=list&t=2`) {
      return makeJsonResponse({ code: 1, list: [{ vod_id: 'classified_proxy' }], class: [] });
    }
    if (url === `${DEFAULT_PROXY_URL}?ac=list&wd=keyword`) {
      return makeJsonResponse({ code: 1, list: [{ vod_id: 'search_proxy' }], class: [] });
    }
    if (url === GITHUB_HOT_TV_URL) {
      return makeGitHubFileResponse(HOT_TV_FIXTURE);
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const classifiedResponse = await worker.fetch(new Request('https://worker.example/api?ac=list&t=2'));
    const classifiedPayload = await classifiedResponse.json();
    assert.deepEqual(classifiedPayload.list, [{ vod_id: 'classified_proxy' }]);

    const searchResponse = await worker.fetch(new Request('https://worker.example/api?ac=list&wd=keyword'));
    const searchPayload = await searchResponse.json();
    assert.deepEqual(searchPayload.list, [{ vod_id: 'search_proxy' }]);

    assert.equal(calls.some((call) => call.url === GITHUB_HOT_TV_URL), false);
  });
});

test('hot_tv GitHub failures keep homepage on Chill-TV instead of falling back to proxy', async () => {
  const worker = (await workerModulePromise).default;

  await runWithFetchStub((url, init) => {
    if (url === GITHUB_HOT_TV_URL) {
      assert.ok(init.signal, 'GitHub fetch should include an abort signal');
      return Promise.reject(makeAbortError('timed out'));
    }
    if (url === `${DEFAULT_PROXY_URL}?ac=detail&ids=tv_hot_1`) {
      return makeJsonResponse({ code: 1, list: [{ vod_id: 'detail_proxy' }], class: [] });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const homepageResponse = await worker.fetch(new Request('https://worker.example/api'));
    const homepagePayload = await homepageResponse.json();
    assert.deepEqual(homepagePayload.list, []);
    assert.deepEqual(homepagePayload.class, []);
    assert.equal(homepagePayload.total, 0);

    const detailResponse = await worker.fetch(new Request('https://worker.example/api?ac=detail&ids=tv_hot_1'));
    const detailPayload = await detailResponse.json();
    assert.deepEqual(detailPayload.list, [{ vod_id: 'detail_proxy' }]);

    assert.equal(calls.filter((call) => call.url === GITHUB_HOT_TV_URL).length, 2);
  });
});

test('config route falls back to built-in config when GitHub config fetch fails', async () => {
  const worker = (await workerModulePromise).default;

  await runWithFetchStub((url, init) => {
    if (url === GITHUB_CONFIG_URL) {
      assert.ok(init.signal, 'GitHub fetch should include an abort signal');
      return Promise.reject(makeAbortError('timed out'));
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const response = await worker.fetch(new Request('https://worker.example/'));
    const payload = await response.json();

    assert.equal(Array.isArray(payload.sites), true);
    assert.equal(payload.sites[0].key, 'chill');
    assert.equal(payload.sites[0].api, 'https://chilltv.chungchung.online/api');
    assert.equal(payload.sites.at(-1).key, 'ry');
    assert.equal(payload.sites.at(-1).api, 'https://chilltv.chungchung.online/p/ry');
    assert.equal('flags' in payload, false);
    assert.equal(calls.filter((call) => call.url === GITHUB_CONFIG_URL).length, 1);
  });
});

test('/p/* routes remain direct proxies and do not read hot_tv.json', async () => {
  const worker = (await workerModulePromise).default;

  await runWithFetchStub((url) => {
    if (url === `${DEFAULT_PROXY_URL}?wd=keyword`) {
      return makeJsonResponse({ code: 1, list: [{ vod_id: 'direct_proxy' }], class: [] });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const response = await worker.fetch(new Request('https://worker.example/p/bfzy?wd=keyword'));
    const payload = await response.json();

    assert.deepEqual(payload.list, [{ vod_id: 'direct_proxy' }]);
    assert.equal(calls.some((call) => call.url === GITHUB_HOT_TV_URL), false);
    assert.deepEqual(calls.map((call) => call.url), [`${DEFAULT_PROXY_URL}?wd=keyword`]);
  });
});

test('/p/ry routes proxy to ruyi upstream', async () => {
  const worker = (await workerModulePromise).default;

  await runWithFetchStub((url) => {
    if (url === 'https://cj.rycjapi.com/api.php/provide/vod?wd=keyword') {
      return makeJsonResponse({ code: 1, list: [{ vod_id: 'ruyi_proxy' }], class: [] });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const response = await worker.fetch(new Request('https://worker.example/p/ry?wd=keyword'));
    const payload = await response.json();

    assert.deepEqual(payload.list, [{ vod_id: 'ruyi_proxy' }]);
    assert.equal(calls.some((call) => call.url === GITHUB_HOT_TV_URL), false);
    assert.deepEqual(calls.map((call) => call.url), ['https://cj.rycjapi.com/api.php/provide/vod?wd=keyword']);
  });
});

test('/img route proxies remote poster assets', async () => {
  const worker = (await workerModulePromise).default;
  const target = 'https://img.example.com/hot-show.jpg';

  await runWithFetchStub((url) => {
    if (url === target) {
      return new Response('image-bytes', {
        status: 200,
        headers: { 'Content-Type': 'image/jpeg' },
      });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }, async (calls) => {
    const response = await worker.fetch(new Request(`https://worker.example/img?url=${encodeURIComponent(target)}`));
    const body = await response.text();

    assert.equal(response.status, 200);
    assert.equal(response.headers.get('Content-Type'), 'image/jpeg');
    assert.equal(body, 'image-bytes');
    assert.deepEqual(calls.map((call) => call.url), [target]);
  });
});
