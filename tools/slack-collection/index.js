import { randomUUID } from 'node:crypto';
import { Plugin, Rpc } from '@opencode/plugin';
import { failureCode } from './failure.mjs';

const toolsByOperation = {
  channels: 'slack_slack_list_user_channels',
  history: 'slack_slack_read_channel',
  search: 'slack_slack_search_public_and_private',
  thread: 'slack_slack_read_thread',
};
const allowedKeys = {
  channels: ['types', 'limit', 'cursor', 'format', 'exclude_archived'],
  history: ['channel_id', 'oldest', 'latest', 'limit', 'cursor', 'response_format'],
  search: ['channel_types', 'keywords', 'filters', 'after', 'before', 'include_bots', 'sort', 'sort_dir', 'limit', 'cursor', 'response_format', 'include_context', 'only_my_channels', 'natural_language_query'],
  thread: ['channel_id', 'message_ts', 'limit', 'cursor', 'response_format'],
};
const empty = { type: 'object', properties: {}, additionalProperties: false };
const rpc = Rpc.define({ id: 'efrenbot-collection', events: {}, methods: {
  capabilities: { input: empty, output: { type: 'object' } },
  read: { input: { type: 'object', additionalProperties: false, properties: {
    session_id: { type: 'string' }, operation: { enum: Object.keys(toolsByOperation) },
    arguments: { type: 'object' },
  }, required: ['session_id', 'operation', 'arguments'] }, output: { type: 'object' } },
} });

export default Plugin.define({ id: 'efrenbot.collection.local-reader', async setup(ctx) {
  const expected = ctx.options.userId;
  async function inventory() {
    const all = await ctx.tool.list();
    const search = all.find(tool => tool.id === toolsByOperation.search);
    const loggedIn = /Current logged in user's user_id is ([UW][A-Z0-9]+)/i.exec(search?.description ?? '');
    const identity = typeof expected === 'string' && loggedIn?.[1] === expected;
    const ready = Object.values(toolsByOperation).every(id => all.filter(t => t.id === id).length === 1);
    return { all, identity, ready };
  }
  await ctx.rpc.register(rpc, {
    capabilities: async () => {
      const { all, identity, ready } = await inventory();
      return { ready: identity && ready, identity_matches: identity,
        input_keys: Object.fromEntries(Object.entries(toolsByOperation).map(([op, id]) =>
          [op, Object.keys(all.find(t => t.id === id)?.input?.properties ?? {})])) };
    },
    read: async (input, rpcContext) => {
      if (ctx.options.enabled !== true) return { error_code: 'reader_disabled' };
      const { all, identity, ready } = await inventory();
      if (!identity || !ready) return { error_code: 'identity_or_capability_changed' };
      const session = await ctx.session.get({ sessionID: input.session_id });
      if (session.agent !== 'build' || session.metadata?.efrenbot_collection !== true ||
          !session.title?.startsWith('Efren Bot collection ')) return { error_code: 'invalid_native_context' };
      if (Object.keys(input.arguments).some(key => !allowedKeys[input.operation].includes(key))) {
        return { error_code: 'invalid_arguments' };
      }
      if (input.operation === 'search' && (input.arguments.only_my_channels !== true || input.arguments.include_context !== false)) {
        return { error_code: 'invalid_search_scope' };
      }
      const reader = all.find(tool => tool.id === toolsByOperation[input.operation]);
      try {
        const result = await reader.execute(input.arguments, {
          sessionID: session.id, agent: 'build', messageID: `msg_efrenbot_collection_${randomUUID()}`,
          id: `call_${randomUUID()}`, signal: AbortSignal.any([rpcContext.signal, AbortSignal.timeout(45000)]),
          progress: async () => {},
        });
        if (result.output && typeof result.output === 'object') return { response: result.output };
        const content = typeof result.content === 'string' ? result.content :
          result.content?.filter(part => part.type === 'text').map(part => part.text).join('\n');
        try { return { response: JSON.parse(content) }; }
        catch { return { error_code: 'unrecognized_tool_envelope' }; }
      } catch (error) { return { error_code: failureCode(error) }; }
    },
  });
} });
