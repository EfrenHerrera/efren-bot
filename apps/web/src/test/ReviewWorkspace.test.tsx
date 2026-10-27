import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ReviewWorkspace } from '@/ReviewWorkspace';
import { dimension } from '@/review-client';
import type { ReviewDraft } from '@/use-review-draft';

const id = '123e4567-e89b-42d3-a456-426614174000';
const second = '123e4567-e89b-42d3-a456-426614174001';
const third = '123e4567-e89b-42d3-a456-426614174002';
const at = '2026-10-26T06:00:00Z';
const base = { id, request_id: id, project_path: 'approved/synthetic', mr_iid: '1', url: 'https://gitlab.com/approved/synthetic/-/merge_requests/1', title: 'Synthetic MR', status: 'ready', phase: 'analyze', revision: 1, error_code: null, created_at: at, updated_at: at };
const finding = { dimension: 'business', path: 'core/example.py', line: 2, severity: 'medium', confidence: 90, problem: 'Synthetic observation', scenario: 'Missing input', impact: 'Failure', alternative: 'Guard before call', comment: 'Can we guard this call?', evidence: [{ source_id: 's1', quote: 'dangerous_call()' }] };
const proposal = { id, item_id: id, revision: 1, version: 1, body: finding.comment, finding, status: 'private', remote_id: null };
const item = { ...base, snapshot: { refs: { head_sha: 'a'.repeat(40), base_sha: 'b'.repeat(40), start_sha: 'b'.repeat(40) }, mr_state: 'opened', sources: [{ id: 's1', kind: 'diff', path: finding.path, sha: 'a'.repeat(40), text: '+dangerous_call()' }], limitations: [], diffs: [{ path: finding.path }] }, plan: {}, report: { summary: 'Static review with cited evidence', checks: dimension.options.map(value => ({ dimension: value, status: 'reviewed', conclusion: 'Inspected static evidence', evidence: finding.evidence })), findings: [finding], previous: [], pending: ['Runtime not executed'], revision: 1 } };
let demo = true;
let fail = false;
let readingLimits: string[] = [];
let proposalText = proposal.body;

beforeEach(() => {
  demo = true; fail = false; readingLimits = []; proposalText = proposal.body;
  vi.stubGlobal('confirm', vi.fn(() => false));
  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (input, init) => {
    const path = String(input);
    if (path.endsWith('/session')) return new Response(JSON.stringify({ token: 'synthetic-token' }));
    if (path.endsWith('/reviews/list')) return new Response(JSON.stringify({ control: { activated_at: at, paused: false, runner_available: true }, projects: ['approved/synthetic'], publication_enabled: true,
      items: [{ ...base, demo, head_sha: 'a'.repeat(40), limitations: [], proposal_count: 1, source_count: 1 }, { ...base, id: second, mr_iid: '2', title: 'Second MR', demo, head_sha: null, limitations: [], proposal_count: 0, source_count: 0 }, { ...base, id: third, mr_iid: '3', title: 'Third MR', demo, head_sha: null, limitations: [], proposal_count: 0, source_count: 0 }], requests: [{ id, demo, status: 'accepted', error_code: null, decision: {} }] }));
    if (path.endsWith('/reviews/detail')) {
      const selected = init?.body === JSON.stringify({ id: second }) ? second : id;
      return new Response(JSON.stringify({ item: { ...item, id: selected, snapshot: { ...item.snapshot, limitations: readingLimits } }, request: { id, demo, channel_id: 'synthetic', message_id: 'source', context: { messages: [{ id, text: 'Review all three' }] } }, proposals: [{ ...proposal, body: proposalText }], entries: [] }));
    }
    return new Response('{}', { status: fail ? 409 : 200 });
  }));
});
afterEach(() => vi.unstubAllGlobals());

describe('Revisiones profundas con decisiones humanas', () => {
  it('muestra todas las MRs y cobertura por dimensión, no una selección inicial', async () => {
    render(<ReviewWorkspace />);
    expect(await screen.findByRole('heading', { name: '3 MRs recientes' })).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: /Análisis/ }));
    expect(await screen.findByText('Arquitectura y responsabilidades')).toBeInTheDocument();
    expect(screen.getByText('Datos, consultas y costo')).toBeInTheDocument();
    expect(screen.getByText('Calidad de las pruebas')).toBeInTheDocument();
    expect(screen.getByText('Contratos y validación')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Resumen' }));
    expect(screen.getByText('Static review with cited evidence')).toBeInTheDocument();
  });
  it('una demo no permite publicar aunque el lector de GitLab esté habilitado', async () => {
    render(<ReviewWorkspace />);
    expect(await screen.findByRole('button', { name: 'Publicar este comentario' })).toBeDisabled();
    expect(fetch).not.toHaveBeenCalledWith('/api/collection/reviews/act', expect.anything());
  });
  it('preserva edición privada si el servidor detecta conflicto de versión', async () => {
    render(<ReviewWorkspace />);
    fireEvent.click(await screen.findByRole('button', { name: 'Editar propuesta' }));
    const field = screen.getByRole('textbox', { name: 'Editar comentario privado' });
    fireEvent.change(field, { target: { value: 'Keep private revision' } });
    fail = true;
    fireEvent.click(screen.getByRole('button', { name: 'Guardar comentario privado' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('La revisión o propuesta cambió');
    expect(field).toHaveValue('Keep private revision');
  });
  it('publicar exige confirmación individual y envía versión exacta, no permiso genérico', async () => {
    demo = false;
    render(<ReviewWorkspace />);
    const button = await screen.findByRole('button', { name: 'Publicar este comentario' });
    fireEvent.click(button);
    expect(fetch).not.toHaveBeenCalledWith('/api/collection/reviews/act', expect.anything());
    vi.stubGlobal('confirm', vi.fn(() => true));
    fireEvent.click(button);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/collection/reviews/act', expect.objectContaining({ body: expect.stringContaining('"proposal_version":1') })));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('No aprueba la MR ni resuelve hilos'));
  });
  it('preguntar no reinicia y cambiar de rumbo es una acción explícita', async () => {
    render(<ReviewWorkspace />);
    fireEvent.click(await screen.findByRole('button', { name: /Conversación/ }));
    const field = await screen.findByRole('textbox', { name: 'Mensaje para esta revisión' });
    fireEvent.change(field, { target: { value: 'What did you trace?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Preguntar sobre el avance' }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/collection/reviews/act', expect.objectContaining({ body: expect.stringContaining('"action":"ask"') })));
    await waitFor(() => expect(field).toHaveValue(''));
  });
  it('conserva mensaje y edición al cambiar de MR y desmontar la pestaña', async () => {
    const drafts = new Map<string, ReviewDraft>();
    const view = render(<ReviewWorkspace drafts={drafts} />);
    fireEvent.click(await screen.findByRole('button', { name: /Conversación/ }));
    fireEvent.change(await screen.findByRole('textbox', { name: 'Mensaje para esta revisión' }), { target: { value: 'Unsent question' } });
    fireEvent.click(screen.getByRole('button', { name: 'Resumen' }));
    fireEvent.click(screen.getByRole('button', { name: 'Editar propuesta' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Editar comentario privado' }), { target: { value: 'Unsent private edit' } });
    fireEvent.click(screen.getByRole('button', { name: /Second MR/ }));
    await waitFor(() => expect(screen.getByRole('button', { name: /Second MR/ })).toHaveAttribute('aria-pressed', 'true'));
    fireEvent.click(await screen.findByRole('button', { name: /Conversación/ }));
    await waitFor(() => expect(screen.getByRole('textbox', { name: 'Mensaje para esta revisión' })).toHaveValue(''));
    fireEvent.click(screen.getByRole('button', { name: /!1 · Synthetic MR/ }));
    expect(await screen.findByRole('textbox', { name: 'Editar comentario privado' })).toHaveValue('Unsent private edit');
    fireEvent.click(screen.getByRole('button', { name: /Conversación/ }));
    expect(screen.getByRole('textbox', { name: 'Mensaje para esta revisión' })).toHaveValue('Unsent question');
    view.unmount();
    render(<ReviewWorkspace drafts={drafts} />);
    expect(await screen.findByRole('textbox', { name: 'Editar comentario privado' })).toHaveValue('Unsent private edit');
    fireEvent.click(screen.getByRole('button', { name: /Conversación/ }));
    expect(screen.getByRole('textbox', { name: 'Mensaje para esta revisión' })).toHaveValue('Unsent question');
  });
  it('muestra el carácter parcial sin desplegar todas las limitaciones', async () => {
    const limitations = ['Diff omitido: core/private/example.py'];
    readingLimits = limitations;
    try {
      const { container } = render(<ReviewWorkspace />);
      const toggle = await screen.findByText(/Límites de lectura/);
      expect(toggle.closest('details')).not.toHaveAttribute('open');
      expect(container.querySelector('.review-panel-nav')).toBeInTheDocument();
      fireEvent.click(toggle);
      expect(toggle.closest('details')).toHaveAttribute('open');
      expect(screen.getByText(limitations[0])).toBeVisible();
    } finally { readingLimits = []; }
  });
  it('formatea el borrador sin alterar el texto que se copia o edita', async () => {
    proposalText = ['¿Usamos **un guard** antes de `dangerous_call()`?', '', '```python', 'if loan:', '    dangerous_call()', '```'].join('\n');
    const writeText = vi.fn(() => Promise.resolve());
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    const { container } = render(<ReviewWorkspace />);
    fireEvent.click(await screen.findByRole('button', { name: 'Copiar borrador' }));
    expect(writeText).toHaveBeenCalledWith(proposalText);
    expect(container.querySelector('.review-comment pre code')).toHaveTextContent('dangerous_call()');
    fireEvent.click(screen.getByRole('button', { name: 'Editar propuesta' }));
    expect(screen.getByRole('textbox', { name: 'Editar comentario privado' })).toHaveValue(proposalText);
  });
  it('abre el código citado con su archivo sin ejecutar otra revisión', async () => {
    render(<ReviewWorkspace />);
    fireEvent.click(await screen.findByRole('button', { name: /Análisis/ }));
    const heading = screen.getByText('Reglas y casos de negocio');
    const check = heading.closest('details');
    if (!check) throw new Error('Missing dimension details');
    fireEvent.click(heading);
    fireEvent.click(within(check).getByText('Ver evidencia · 1'));
    expect(within(check).getByText('core/example.py')).toBeVisible();
    expect(within(check).getByLabelText('Código, Diff')).toHaveTextContent('dangerous_call()');
    expect(fetch).not.toHaveBeenCalledWith('/api/collection/reviews/act', expect.anything());
  });
});
