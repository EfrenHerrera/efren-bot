import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import type { IncomingMessage } from 'node:http';
import { PassThrough } from 'node:stream';
import { test } from 'vitest';

import { createApp } from './app.js';
import { parseConfig } from './config.js';
import { createRootLogger, type AppLogger } from './logger.js';
import { sanitize, sanitizeText } from './sanitize.js';

const secret = 'private-marker';
const secretUrl = `https://private-user:private-password@example.test/callback?unknown=${secret}#private-fragment`;
const headers = {
  authorization: `Bearer ${secret}`,
  cookie: `session=${secret}`,
  'x-private-header': secret,
};
const config = parseConfig({ REQUEST_TIMEOUT_MS: '25' });
const credentials = {
  client_id: secret,
  client_secret: secret,
  code: secret,
  state: secret,
  code_verifier: secret,
  code_challenge: secret,
  refresh_token: secret,
  redirect_uri: secretUrl,
  unknown: secret,
};

function captureLogger() {
  const entries: unknown[] = [];
  const root = createRootLogger('trace', {
    write: (chunk: string) => entries.push({ emitted: JSON.parse(chunk) }),
  });
  function logger(bindings: Record<string, unknown> = {}): AppLogger {
    const output = root.child(bindings);
    const record = (level: 'info' | 'error' | 'warn') => (fields: unknown, message?: string) => {
      entries.push({ bindings, fields, message });
      output[level](fields as object, message);
    };
    return {
      child: (childBindings: Record<string, unknown>) => logger({ ...bindings, ...childBindings }),
      info: record('info'),
      error: record('error'),
      warn: record('warn'),
    } as unknown as AppLogger;
  }
  return { rootLogger: logger(), entries };
}

function assertPrivate(entries: unknown[]) {
  const serialized = JSON.stringify(entries);
  assert.ok(entries.length > 0, 'operational logs must remain enabled');
  assert.doesNotMatch(serialized, /private(?:-|%2d)/i);
  assert.doesNotMatch(serialized, /requestBody|requestHeaders|wwwAuthenticate/);
}

function nodeModule(fail: boolean, status = 200) {
  return {
    request: (_options: unknown, callback: (response: IncomingMessage) => void) => {
      const request = new EventEmitter() as EventEmitter & {
        setTimeout: () => unknown;
        write: () => void;
        end: () => void;
        destroy: () => void;
      };
      request.setTimeout = () => request;
      request.write = () => {};
      request.end = () => {
        queueMicrotask(() => {
          if (fail) {
            request.emit('error', new Error(`Failed ${secretUrl} ${secret}`));
          } else {
            const response = new PassThrough() as PassThrough & {
              statusCode: number;
              headers: Record<string, string>;
            };
            response.statusCode = status;
            response.headers = {
              'set-cookie': `session=${secret}`,
              'www-authenticate': `Bearer error_description="${secretUrl}"`,
              location: secretUrl,
            };
            response.end(secret);
            callback(response as unknown as IncomingMessage);
          }
        });
      };
      request.destroy = () => request.emit('error', new Error(secret));
      return request;
    },
  };
}

test('authorize logs exclude query, fragment, userinfo and nested redirect credentials', async () => {
  const capture = captureLogger();
  const app = createApp({ config, rootLogger: capture.rootLogger });
  const response = await app.request(
    `http://localhost/oauth/authorize?${new URLSearchParams(credentials)}#private-fragment`,
  );
  assert.equal(response.status, 302);
  assert.equal(new URL(response.headers.get('location')!).searchParams.get('state'), secret);
  assertPrivate(capture.entries);
  assert.match(JSON.stringify(capture.entries), /GET|authorize/);
});

for (const path of ['/callback', '/mcp', '/mcp/private-path']) {
  for (const fail of [false, true]) {
    test(`${path} ${fail ? 'error' : 'success'} logs exclude headers, query, body and error details`, async () => {
      const capture = captureLogger();
      const app = createApp({
        config,
        rootLogger: capture.rootLogger,
        dependencies: { httpModule: nodeModule(fail), httpsModule: nodeModule(fail) },
      });
      const response = await app.request(
        `http://localhost${path}?${new URLSearchParams(credentials)}`,
        { method: 'POST', headers, body: JSON.stringify({ text: secret, id: secret }) },
        { incoming: { headers } as unknown as IncomingMessage },
      );
      assert.equal(response.status, fail ? 502 : 200);
      await response.text();
      assertPrivate(capture.entries);
      assert.match(JSON.stringify(capture.entries), /POST/);
      if (!fail) assert.match(JSON.stringify(capture.entries), /"status":200/);
    });
  }
}

for (const encoding of ['json', 'form', 'query']) {
  for (const status of [200, 400]) {
    test(`token ${encoding} ${status} logs exclude credentials and arbitrary response bodies`, async () => {
      const capture = captureLogger();
      const app = createApp({
        config,
        rootLogger: capture.rootLogger,
        dependencies: {
          fetcher: async (_url, init) => {
            assert.equal(new URLSearchParams(String(init?.body)).get('code_verifier'), secret);
            return new Response(JSON.stringify({ access_token: secret, unknown: secret }), {
              status,
              headers: { 'set-cookie': secret, location: secretUrl },
            });
          },
        },
      });
      const response = await app.request(
        `http://localhost/oauth/token?${new URLSearchParams(credentials)}`,
        {
          method: 'POST',
          headers: {
            ...headers,
            'content-type':
              encoding === 'json' ? 'application/json' : 'application/x-www-form-urlencoded',
          },
          body:
            encoding === 'query'
              ? ''
              : encoding === 'json'
                ? JSON.stringify(credentials)
                : new URLSearchParams(credentials).toString(),
        },
      );
      assert.equal(response.status, status);
      assert.match(await response.text(), /private-marker/);
      assertPrivate(capture.entries);
      assert.match(JSON.stringify(capture.entries), new RegExp(`"status":${status}`));
    });
  }
}

test('token network failures never log exception messages, URLs or nested causes', async () => {
  const capture = captureLogger();
  const app = createApp({
    config,
    rootLogger: capture.rootLogger,
    dependencies: {
      fetcher: async () => {
        throw new Error(secretUrl, { cause: new Error(secret) });
      },
    },
  });
  const response = await app.request('http://localhost/oauth/token', { method: 'POST' });
  assert.equal(response.status, 502);
  assertPrivate(capture.entries);
});

test('malformed token JSON never logs parser messages or request content', async () => {
  const capture = captureLogger();
  const app = createApp({ config, rootLogger: capture.rootLogger });
  const response = await app.request('http://localhost/oauth/token', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: `{"private-marker":`,
  });
  assert.equal(response.status, 502);
  assertPrivate(capture.entries);
});

test('discovery opaque error bodies are absent from application error logs', async () => {
  const capture = captureLogger();
  const app = createApp({
    config,
    rootLogger: capture.rootLogger,
    dependencies: { jsonFetcher: async () => new Response(secretUrl, { status: 400 }) },
  });
  const response = await app.request('http://localhost/.well-known/oauth-authorization-server');
  assert.equal(response.status, 502);
  assertPrivate(capture.entries);
});

for (const path of ['oauth-protected-resource', 'oauth-authorization-server']) {
  for (const status of [200, 400]) {
    test(`discovery ${path} ${status} does not log remote metadata or error bodies`, async () => {
      const capture = captureLogger();
      const app = createApp({
        config,
        rootLogger: capture.rootLogger,
        dependencies: {
          jsonFetcher: async () => new Response(JSON.stringify({ unknown: secret }), { status }),
        },
      });
      const response = await app.request(`http://localhost/.well-known/${path}`);
      assert.equal(response.status, status === 200 ? 200 : 502);
      assertPrivate(capture.entries);
    });
  }
}

test('legacy sanitizer masks state and PKCE in JSON, form and nested URL values', () => {
  const values = { state: secret, code_verifier: secret, code_challenge: secret };
  for (const value of [
    sanitize({ nested: values }),
    sanitizeText(JSON.stringify(values)),
    sanitizeText(new URLSearchParams(values).toString()),
    sanitizeText('%73tate=private%2dmarker&code_verifier=private%2dmarker'),
    sanitizeText(`Failed to fetch ${secretUrl}`),
    sanitizeText('{"code_verifier":"private-marker"'),
    sanitize({ nested: { url: secretUrl } }),
    sanitize({
      headers: { authorization: secret, cookie: secret, 'set-cookie': secret },
      nested: [new URL(secretUrl), new Error(secret)],
    }),
  ]) {
    assert.doesNotMatch(JSON.stringify(value), /private/);
  }
});

test('real logger allowlists bindings and fields without disabling useful operational logs', () => {
  const lines: string[] = [];
  const root = createRootLogger('trace', { write: (line: string) => lines.push(line) });
  const logger = root.child({ component: 'callback', authorization: secret, nested: credentials });
  logger.error(
    {
      status: 502,
      method: 'POST',
      path: '/callback',
      timeoutMs: 25,
      message: secretUrl,
      err: new Error(secretUrl, { cause: new Error(secret) }),
      body: { text: secret, id: secret },
      headers,
      nested: { url: secretUrl },
    },
    'Safe failure event',
  );
  logger.info({ method: secret, path: secretUrl, status: secret }, 'Safe event');
  assert.doesNotMatch(lines.join(''), /private/);
  const event = JSON.parse(lines[0]);
  assert.equal(event.component, 'callback');
  assert.equal(event.method, 'POST');
  assert.equal(event.path, '/callback');
  assert.equal(event.status, 502);
  assert.equal(event.timeoutMs, 25);
  assert.equal(event.level, 50);
});
