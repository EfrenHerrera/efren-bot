import { z } from 'zod';

const admission = z.object({ decision: z.string(), decided_by: z.string(), reasons: z.array(z.string()),
  project: z.string().nullable(), profile: z.string().nullable(), role: z.string().nullable() });
const item = z.object({ id: z.string().uuid(), source: z.string(), external_id: z.string(), title: z.string(),
  text: z.string(), status: z.string(), url: z.string().nullable(), occurred_at: z.string(), admission: admission.nullable() });
const job = z.object({ id: z.string().uuid(), key: z.string(), item_id: z.string().uuid(), project: z.string(),
  status: z.string(), attempts: z.number().int(), error_code: z.string().nullable(), risk: z.string().nullable().optional(),
  requires_human: z.boolean().nullable().optional(), human_reasons: z.array(z.string()), branch: z.string().nullable().optional(),
  checks: z.array(z.object({ name: z.string(), status: z.string(), mandatory: z.boolean() })), review: z.string().nullable().optional() });
const effect = z.object({ id: z.string().uuid(), job_id: z.string().uuid(), kind: z.string(), policy: z.string(),
  state: z.string(), payload: z.record(z.string(), z.unknown()), fingerprint: z.string().length(64),
  expires_at: z.string(), decided_by: z.string().nullable(), result: z.record(z.string(), z.unknown()).nullable() });
export const factoryList = z.object({ items_by_status: z.record(z.string(), z.number().int()),
  awaiting_admission: z.array(item), jobs: z.array(job), pending_effects: z.array(effect),
  projects: z.array(z.object({ name: z.string(), profile: z.string() })) });
export type FactoryList = z.infer<typeof factoryList>;
export type FactoryItem = z.infer<typeof item>;
export type FactoryJob = z.infer<typeof job>;
export type FactoryEffect = z.infer<typeof effect>;
export const effectLabels: Record<string, string> = { open_pr: 'Abrir merge request', update_notion: 'Actualizar tarea en Notion', post_slack: 'Responder en Slack' };
export const jobLabels: Record<string, string> = { queued: 'En cola', running: 'En ejecución', paused: 'Pausado', succeeded: 'Terminado', failed: 'Falló', blocked: 'Bloqueado', cancelled: 'Detenido', superseded: 'Reorientado' };
export const riskLabels: Record<string, string> = { passive: 'Riesgo bajo', medium: 'Riesgo medio', high: 'Riesgo alto' };
