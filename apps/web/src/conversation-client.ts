import { z } from 'zod';
import { attentionSchema, categorySchema, inboxMessageSchema } from '@/collection-client';

const timestamp = z.string().datetime({ offset: true });
export const conversationView = z.enum(['all', 'mentions', 'following', 'new']);
export const contextMessageSchema = inboxMessageSchema.extend({ mentions_me: z.boolean(), mention_excerpt: z.string().nullable() });
export const conversationSchema = z.object({
  id: z.string().uuid(), source_scope: z.string(), channel_id: z.string(), channel_name: z.string(),
  conversation_id: z.string(), preview: z.string(), root_present: z.boolean(),
  relation_status: z.enum(['confirmed', 'unlinked', 'conflict']),
  message_count: z.number().int().positive(), mention_count: z.number().int().nonnegative(),
  new_count: z.number().int().nonnegative(), group_count: z.number().int().nonnegative(),
  last_activity_at: timestamp,
  mention_previews: z.array(z.object({ id: z.string().uuid(), excerpt: z.string() })),
});
export const groupSchema = z.object({
  id: z.string().uuid(), title: z.string(), category: categorySchema, attention: attentionSchema,
  revision: z.number().int().positive(), message_ids: z.array(z.string().uuid()),
  evidence_count: z.number().int().nonnegative(), all_context: z.boolean(),
});
export const conversationListSchema = z.object({
  conversations: z.array(conversationSchema), total: z.number().int().nonnegative(),
  offset: z.number().int().nonnegative(), next_offset: z.number().int().nonnegative().nullable(), snapshot_at: timestamp,
  channels: z.array(z.object({ channel_id: z.string(), channel_name: z.string() })),
});
export const conversationDetailSchema = z.object({
  self_user_id: z.string().regex(/^[UW][A-Z0-9]+$/),
  conversation: conversationSchema.extend({ root: contextMessageSchema.nullable() }),
  groups: z.array(groupSchema), messages: z.array(contextMessageSchema),
  total: z.number().int().nonnegative(), offset: z.number().int().nonnegative(),
  next_offset: z.number().int().nonnegative().nullable(), snapshot_at: timestamp,
  mention_locations: z.array(z.object({ id: z.string().uuid(), offset: z.number().int().nonnegative(), excerpt: z.string() })),
});
export type Conversation = z.infer<typeof conversationSchema>;
export type ConversationDetail = z.infer<typeof conversationDetailSchema>;
export type ContextMessage = z.infer<typeof contextMessageSchema>;
export type Group = z.infer<typeof groupSchema>;
export type ConversationFilters = { view: z.infer<typeof conversationView>; query: string; channel_id: string; category: z.infer<typeof categorySchema> | ''; attention: z.infer<typeof attentionSchema> | '' };
export type GroupDraft = { id?: string; revision?: number; request_id: string; title: string; category: z.infer<typeof categorySchema>; attention: z.infer<typeof attentionSchema>; message_ids: string[] };
export function conversationKey(value: Conversation) { return JSON.stringify([value.source_scope, value.channel_id, value.conversation_id, value.relation_status === 'conflict']); }
