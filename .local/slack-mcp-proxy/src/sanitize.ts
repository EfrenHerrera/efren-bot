import { REDACTED, REDACTED_KEYS } from './constants.js';

function maskValue(key: string | undefined, value: unknown): unknown {
  if (value === undefined || value === null) {
    return value;
  }

  if (key && REDACTED_KEYS.has(key.toLowerCase())) {
    return REDACTED;
  }

  return value;
}

export function sanitize(value: unknown, parentKey?: string): unknown {
  if (parentKey && REDACTED_KEYS.has(parentKey.toLowerCase())) {
    return maskValue(parentKey, value);
  }

  if (value instanceof Error) {
    return REDACTED;
  }

  if (value instanceof URL) {
    return `${value.origin}${value.pathname}`;
  }

  if (typeof value === 'string' && /^https?:\/\//i.test(value)) {
    try {
      const url = new URL(value);
      return `${url.origin}${url.pathname}`;
    } catch {
      return REDACTED;
    }
  }

  if (Array.isArray(value)) {
    return value.map((entry) => sanitize(entry, parentKey));
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, entry]) => [key, sanitize(maskValue(key, entry), key)]),
    );
  }

  return maskValue(parentKey, value);
}

export function sanitizeText(text: string): unknown {
  if (!text) {
    return text;
  }

  try {
    return sanitize(JSON.parse(text));
  } catch {
    // Opaque response/error text is not safe to log, even after key-based masking.
    return REDACTED;
  }
}

// Logging is an allowlist, not a best-effort scrub of arbitrary request data.
// Callers must use constant event messages and must never pass bodies/headers.
export function sanitizeLogMetadata(value: Record<string, unknown> = {}): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  const allowedStrings: Record<string, readonly string[]> = {
    component: ['mcp-proxy', 'callback', 'oauth-discovery', 'authorize', 'token', 'app-error'],
    method: ['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    path: [
      '/mcp',
      '/mcp/*',
      '/callback',
      '/oauth/authorize',
      '/oauth/token',
      '/.well-known/oauth-protected-resource',
      '/.well-known/oauth-authorization-server',
    ],
    signal: ['SIGINT', 'SIGTERM'],
  };

  for (const [key, allowed] of Object.entries(allowedStrings)) {
    if (typeof value[key] === 'string' && allowed.includes(value[key])) {
      result[key] = value[key];
    }
  }

  if (
    Number.isInteger(value.status) &&
    Number(value.status) >= 100 &&
    Number(value.status) <= 599
  ) {
    result.status = value.status;
  }
  if (
    Number.isInteger(value.timeoutMs) &&
    Number(value.timeoutMs) >= 0 &&
    Number(value.timeoutMs) <= 2_147_483_647
  ) {
    result.timeoutMs = value.timeoutMs;
  }

  return result;
}
