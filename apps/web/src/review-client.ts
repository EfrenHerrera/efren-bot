import { z } from 'zod';

const timestamp = z.string().datetime({ offset: true });
export const reviewStatus = z.enum(['queued', 'running', 'ready', 'partial', 'blocked', 'paused', 'failed']);
export const reviewPhase = z.enum(['capture', 'plan', 'context', 'analyze']);
export const dimension = z.enum(['architecture', 'clean_code', 'data_cost', 'contracts', 'business', 'security', 'tests', 'integration']);
const citation = z.object({ source_id: z.string(), quote: z.string() });
const check = z.object({ dimension, status: z.enum(['reviewed', 'limited', 'not_applicable']), conclusion: z.string(), evidence: z.array(citation) });
export const finding = z.object({ dimension, path: z.string(), line: z.number().int(), severity: z.enum(['high', 'medium', 'low']), confidence: z.number().int(), problem: z.string(), scenario: z.string(), impact: z.string(), alternative: z.string(), comment: z.string(), evidence: z.array(citation) });
const report = z.object({ summary: z.string().optional(), checks: z.array(check).optional(), findings: z.array(finding).optional(), previous: z.array(z.object({ discussion_id: z.string(), assessment: z.string(), status: z.string(), evidence: z.array(citation) })).optional(), pending: z.array(z.string()).optional(), revision: z.number().int().optional() });
const source = z.object({ id: z.string(), kind: z.string(), text: z.string(), path: z.string().optional(), sha: z.string().optional(), line_start: z.number().int().optional() });
const itemBase = z.object({ id: z.string().uuid(), request_id: z.string().uuid(), project_path: z.string(), mr_iid: z.string(), url: z.string().url().startsWith('https://gitlab.com/'), title: z.string(), status: reviewStatus, phase: reviewPhase, revision: z.number().int(), error_code: z.string().nullable(), created_at: timestamp, updated_at: timestamp });
export const reviewList = z.object({
  control: z.object({ activated_at: timestamp.nullable(), paused: z.boolean(), runner_available: z.boolean() }), projects: z.array(z.string()), publication_enabled: z.boolean(),
  items: z.array(itemBase.extend({ demo: z.boolean(), head_sha: z.string().nullable(), limitations: z.array(z.string()), proposal_count: z.number().int(), source_count: z.number().int() })),
  requests: z.array(z.object({ id: z.string().uuid(), demo: z.boolean(), status: z.string(), error_code: z.string().nullable(), decision: z.object({ reason: z.string().optional() }) })),
});
export const reviewDetail = z.object({
  item: itemBase.extend({ snapshot: z.object({ refs: z.object({ head_sha: z.string(), base_sha: z.string(), start_sha: z.string() }).optional(), mr_state: z.string().optional(), sources: z.array(source).optional(), limitations: z.array(z.string()).optional(), diffs: z.array(z.object({ path: z.string() })).optional() }), plan: z.object({ objective: z.string().optional(), reads: z.array(z.object({ path: z.string(), side: z.string(), start: z.number().int(), end: z.number().int(), reason: z.string(), item_id: z.string() })).optional(), hypotheses: z.array(z.string()).optional() }), report }),
  request: z.object({ id: z.string().uuid(), demo: z.boolean(), channel_id: z.string(), message_id: z.string(), context: z.object({ messages: z.array(z.object({ id: z.string().uuid(), text: z.string() })) }) }),
  proposals: z.array(z.object({ id: z.string().uuid(), item_id: z.string().uuid(), revision: z.number().int(), version: z.number().int(), body: z.string(), finding, status: z.string(), remote_id: z.string().nullable() })),
  entries: z.array(z.object({ id: z.string().uuid(), kind: z.string(), status: z.string(), text: z.string(), created_at: timestamp })),
});
export type ReviewList = z.infer<typeof reviewList>;
export type ReviewDetail = z.infer<typeof reviewDetail>;
export type Proposal = ReviewDetail['proposals'][number];
export type ReviewAction = 'ask' | 'redirect' | 'pause' | 'resume' | 'discard' | 'edit' | 'publish';
export const dimensionLabels: Record<z.infer<typeof dimension>, string> = { architecture: 'Arquitectura y responsabilidades', clean_code: 'Clean Code con impacto', data_cost: 'Datos, consultas y costo', contracts: 'Contratos y validación', business: 'Reglas y casos de negocio', security: 'Seguridad y permisos', tests: 'Calidad de las pruebas', integration: 'Dependencias e integración entre MRs' };
export const phaseLabels: Record<z.infer<typeof reviewPhase>, string> = { capture: 'Capturando MR, versión y discusiones', plan: 'Trazando hipótesis y lecturas', context: 'Leyendo dependencias autorizadas', analyze: 'Contrastando evidencia y redactando propuestas' };
export const reviewLabels: Record<z.infer<typeof reviewStatus>, string> = { queued: 'En cola', running: 'Revisando', ready: 'Propuestas listas para decidir', partial: 'Revisión parcial: falta evidencia', blocked: 'Acceso no autorizado', paused: 'Pausada por ti', failed: 'No se completó' };
