import { z } from 'zod';

const timestamp = z.string().datetime({ offset: true });
export const supportStatus = z.enum(['queued', 'analyzing', 'blocked', 'paused', 'dismissed', 'failed']);
export const supportAction = z.enum(['ask', 'redirect', 'pause', 'resume', 'dismiss']);
const contextSchema = z.object({
  conversation_id: z.string(), channel_name: z.string(), trigger_id: z.string().uuid(),
  root_present: z.boolean(), relation_status: z.string(), truncated: z.boolean(),
  messages: z.array(z.object({ id: z.string().uuid(), text: z.string(), occurred_at: timestamp })),
});
const reportSchema = z.object({
  reported: z.array(z.string()).optional(), hypotheses: z.array(z.string()).optional(),
  missing: z.array(z.string()).optional(), evidence_ids: z.array(z.string()).optional(),
  slack_draft: z.string().optional(), coverage: z.literal('slack_only').optional(),
  revision: z.number().int().optional(),
});
export const supportCase = z.object({
  id: z.string().uuid(), anchor_id: z.string().uuid(), title: z.string(), status: supportStatus,
  revision: z.number().int(), context: contextSchema, report: reportSchema,
  error_code: z.string().nullable(), created_at: timestamp, updated_at: timestamp,
});
export const supportList = z.object({
  control: z.object({ activated_at: timestamp.nullable(), paused: z.boolean(), runner_available: z.boolean() }),
  source_limits: z.record(z.string(), z.string()),
  cases: z.array(supportCase.omit({ context: true, report: true }).extend({
    context: z.object({ channel_name: z.string() }),
  })),
  intakes: z.array(z.object({ id: z.string().uuid(), status: z.string(), error_code: z.string().nullable(),
    decision: z.object({ action: z.string().optional(), reason: z.string().optional() }) })),
});
export const supportDetail = z.object({
  case: supportCase,
  entries: z.array(z.object({ id: z.string().uuid(), kind: z.string(), text: z.string(), status: z.string(), created_at: timestamp })),
});
export type SupportList = z.infer<typeof supportList>;
export type SupportDetail = z.infer<typeof supportDetail>;
export type SupportAction = z.infer<typeof supportAction>;
export const supportLabels: Record<z.infer<typeof supportStatus>, string> = {
  queued: 'En cola', analyzing: 'Analizando contexto', blocked: 'Faltan fuentes autorizadas',
  paused: 'Pausada', dismissed: 'Descartada por ti', failed: 'No se completó',
};
