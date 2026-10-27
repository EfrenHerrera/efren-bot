import assert from 'node:assert/strict';
import test from 'node:test';
import { failureCode } from './failure.mjs';

test('returns only closed error codes, never remote/private messages', () => {
  for (const [message, code] of [
    ['rate_limited token=synthetic-private', 'source_rate_limited'],
    ['channel_not_found private-channel-name', 'channel_unavailable'],
    ['invalid_arguments user-text', 'source_arguments_invalid'],
    ['missing_scope synthetic-secret', 'source_permission_denied'],
    ['unknown synthetic-secret', 'source_read_failed'],
  ]) assert.equal(failureCode(new Error(message)), code);
});
