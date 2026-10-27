export function failureCode(error) {
  const messages = [];
  const seen = new Set();
  function visit(value, depth = 0) {
    if (!value || depth > 4 || seen.has(value)) return;
    if (typeof value === 'string') { messages.push(value.slice(0, 2000)); return; }
    if (typeof value !== 'object') return;
    seen.add(value);
    for (const key of ['message', 'error', 'cause', 'defect']) visit(value[key], depth + 1);
  }
  visit(error);
  const text = messages.join(' ');
  if (/rate.?limit|too_many_requests|429|retry.after/i.test(text)) return 'source_rate_limited';
  if (/channel_not_found|not_in_channel|conversation_not_found/i.test(text)) return 'channel_unavailable';
  if (/invalid_auth|not_authed|token_expired/i.test(text)) return 'source_auth_unavailable';
  if (/invalid_argument|invalid_input|validation|invalid.*timestamp/i.test(text)) return 'source_arguments_invalid';
  if (/missing_scope|permission|forbidden|denied/i.test(text)) return 'source_permission_denied';
  return 'source_read_failed';
}
