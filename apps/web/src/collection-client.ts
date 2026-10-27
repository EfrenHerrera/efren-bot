import { z } from 'zod';

export const runStatus = z.enum(['queued', 'running', 'succeeded', 'partial', 'failed']);
export const actionSchema = z.enum(['activate', 'pause', 'resume', 'run']);
const timestamp = z.string().datetime({ offset: true });
const runSchema = z.object({
  id: z.string().uuid(), trigger: z.enum(['manual', 'automatic', 'import']), status: runStatus,
  created_at: timestamp, started_at: timestamp.nullable(), finished_at: timestamp.nullable(),
  window_start: timestamp, window_end: timestamp.nullable(), added_count: z.number().int().nonnegative(),
  page_count: z.number().int().nonnegative(), error_code: z.string().nullable(),
  coverage: z.array(z.object({ scope: z.string(), state: z.string(), code: z.string().optional() })),
});
export const collectionSchema = z.object({
  activated_at: timestamp.nullable(), paused: z.boolean(), next_due_at: timestamp.nullable(),
  watermark: timestamp.nullable(), runner_seen_at: timestamp.nullable(), runner_available: z.boolean(),
  active_run: runSchema.nullable(), runs: z.array(runSchema), message_count: z.number().int().nonnegative(),
  interval_seconds: z.number().int().positive(),
  messages: z.array(z.object({ id: z.string().uuid(), source_scope: z.string(), channel_id: z.string(),
    channel_name: z.string(), message_id: z.string(), thread_id: z.string().nullable(),
    actor_id: z.string().nullable(), text: z.string(), occurred_at: timestamp, observed_at: timestamp,
    source_url: z.string().regex(/^https:\/\/[a-z0-9-]+\.(?:enterprise\.)?slack\.com\//).nullable(),
  })),
});
export type Collection = z.infer<typeof collectionSchema>;
export type CollectionAction = z.infer<typeof actionSchema>;
export type RunStatus = z.infer<typeof runStatus>;

let token: string | null = null;

export async function collectionRequest(path: string, method = 'GET', signal?: AbortSignal, body: unknown = {}): Promise<unknown> {
  if (!token) {
    const session = await fetch('/api/collection/session', { signal, cache: 'no-store', headers: { 'X-Efren-Local': '1' } });
    if (!session.ok) throw new Error('session_unavailable');
    token = z.object({ token: z.string().min(1) }).parse(await session.json()).token;
  }
  const response = await fetch(`/api/collection/${path}`, {
    method, signal, cache: 'no-store', headers: { 'X-Efren-Local': '1', 'X-Collection-Token': token,
      ...(method === 'POST' ? { 'Content-Type': 'application/json' } : {}) },
    ...(method === 'POST' ? { body: JSON.stringify(body) } : {}),
  });
  if (response.status === 401) token = null;
  if (!response.ok) throw new Error(response.status === 409 ? 'collection_conflict' : 'collection_unavailable');
  return response.json();
}

export const categorySchema = z.enum(['unclassified', 'support', 'code_review', 'coordination', 'information']);
export const attentionSchema = z.enum(['undecided', 'required', 'not_required']);
export const reviewSchema = z.enum(['all', 'new', 'unreviewed', 'reviewed']);
export const originSchema = z.enum(['all', 'historical', 'live']);
export const modeSchema = z.enum(['full', 'mentions', 'off']);
export type Category = z.infer<typeof categorySchema>;
export type Attention = z.infer<typeof attentionSchema>;
export type Review = z.infer<typeof reviewSchema>;
export type Origin = z.infer<typeof originSchema>;
export const categories: Record<Category, string> = { unclassified: 'Sin clasificar', support: 'Soporte', code_review: 'Revisión de código', coordination: 'Coordinación', information: 'Información' };
export const attentions: Record<Attention, string> = { undecided: 'Por decidir', required: 'Requiere atención', not_required: 'No requiere atención' };
export const modes: Record<z.infer<typeof modeSchema>, string> = { full: 'Todos los mensajes', mentions: 'Solo mis menciones e hilos', off: 'Desactivado' };
export const inboxMessageSchema = z.object({
  id: z.string().uuid(), source_scope: z.string(), channel_id: z.string(), channel_name: z.string(),
  message_id: z.string(), thread_id: z.string().nullable(), actor_id: z.string().nullable(),
  text: z.string(), occurred_at: timestamp, observed_at: timestamp,
  source_url: z.string().regex(/^https:\/\/[a-z0-9-]+\.(?:enterprise\.)?slack\.com\//).nullable(),
  historical: z.boolean(), variant_count: z.number().int().positive(), reviewed: z.boolean(),
  reviewed_at: timestamp.nullable(), is_new: z.boolean(), category: categorySchema, attention: attentionSchema,
});
export const inboxSchema = z.object({
  messages: z.array(inboxMessageSchema), total: z.number().int().nonnegative(), snapshot_at: timestamp,
  offset: z.number().int().nonnegative(), next_offset: z.number().int().nonnegative().nullable(),
  channels: z.array(z.object({ channel_id: z.string(), channel_name: z.string() })),
});
export const threadSchema = z.object({ messages: z.array(inboxMessageSchema), total: z.number().int().nonnegative(), next_offset: z.number().int().nonnegative().nullable() });
export const variantsSchema = z.object({ messages: z.array(z.object({ id: z.string().uuid(), text: z.string(), observed_at: timestamp, is_historical: z.boolean() })), total: z.number().int().nonnegative(), next_offset: z.number().int().nonnegative().nullable() });
export const sourcesSchema = z.object({ observed_at: timestamp.nullable(), channels: z.array(z.object({ channel_id: z.string(), channel_name: z.string(), available: z.boolean(), mode: modeSchema, since: timestamp.nullable() })) });
export type InboxMessage = z.infer<typeof inboxMessageSchema>;
export type Inbox = z.infer<typeof inboxSchema>;
export type Sources = z.infer<typeof sourcesSchema>;
export type Source = Sources['channels'][number];
export type Filters = { channel_id: string; query: string; review: Review; origin: Origin; category: Category | ''; attention: Attention | '' };
