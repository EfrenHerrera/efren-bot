import { z } from 'zod';

export const domain = z.enum(['support', 'review']);
export const disposition = z.enum(['active', 'paused', 'ignored', 'delegated', 'stopped']);
const action = z.object({ id: z.string().uuid(), kind: z.string(), label: z.string(), body: z.string(),
  destination: z.string(), version: z.number().int().nullable(), enabled: z.boolean(),
  reason: z.string(), fingerprint: z.string().length(64), denied: z.boolean(),
  refs: z.object({ base_sha: z.string(), head_sha: z.string(), start_sha: z.string() }).optional(),
  position: z.object({ path: z.string(), line: z.number().int() }).optional(),
  expires_in_seconds: z.number().int().optional() });
const request = z.object({ domain, id: z.string().uuid(), title: z.string(), status: z.string(),
  revision: z.number().int(), control_revision: z.number().int(), disposition,
  category: z.enum(['inactive', 'decision', 'conclusion', 'working']), conclusion: z.string(),
  report_revision: z.number().int().nullable(), pending: z.array(z.string()), actions: z.array(action),
  updated_at: z.string().datetime({ offset: true }), error_code: z.string().nullable() });
const control = z.object({ activated_at: z.string().datetime({ offset: true }).nullable(),
  paused: z.boolean(), available: z.boolean(), queued: z.number().int() });
export const humanList = z.object({ items: z.array(request), controls: z.object({ support: control, review: control }),
  capabilities: z.array(z.object({ kind: z.string(), label: z.string(), enabled: z.boolean(), reason: z.string() })),
  limit_per_domain: z.number().int() });
export const humanDetail = z.object({ request, report: z.record(z.string(), z.unknown()), snapshot: z.record(z.string(), z.unknown()), history: z.array(z.object({ id: z.string().uuid(),
  input: z.object({ action: z.string(), text: z.string(), revision: z.number().int() }),
  created_at: z.string().datetime({ offset: true }) })) });
export type HumanRequest = z.infer<typeof request>;
export type HumanList = z.infer<typeof humanList>;
export type HumanDetail = z.infer<typeof humanDetail>;
export type HumanAction = z.infer<typeof action>;
export type HumanChoice = 'attend' | 'continue' | 'redirect' | 'pause' | 'ignore' | 'delegate' | 'stop' | 'approve' | 'deny';
export type HumanFilter = 'decision' | 'working' | 'conclusion' | 'inactive' | 'all';
export type HumanDraft = { text: string; revision: number; control_revision: number; request_id: string };
export const dispositionLabels = { active: 'Seguimiento activo', paused: 'Pausada', ignored: 'No atender', delegated: 'Delegada', stopped: 'Detenida' };
export const choiceLabels = { attend: 'Atender', continue: 'Continuar', redirect: 'Reorientar', pause: 'Pausar', ignore: 'No atender', delegate: 'Delegar', stop: 'Detener', approve: 'Autorizar acción', deny: 'Denegar acción' };
export const filterLabels: Record<HumanFilter, string> = { decision: 'Necesita decisión', working: 'En curso', conclusion: 'Conclusiones', inactive: 'Delegadas / pausadas', all: 'Todas' };
export function requestKey(item: HumanRequest) { return `${item.domain}:${item.id}`; }
export function matches(item: HumanRequest, filter: HumanFilter) {
  if (filter === 'all') return true;
  if (filter === 'conclusion') return Boolean(item.conclusion);
  return item.category === filter;
}
