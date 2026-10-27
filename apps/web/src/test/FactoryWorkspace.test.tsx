import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FactoryWorkspace } from '@/FactoryWorkspace';

const itemId = '123e4567-e89b-42d3-a456-426614174000';
const jobId = '123e4567-e89b-42d3-a456-426614174001';
const effectId = '123e4567-e89b-42d3-a456-426614174002';
const fingerprint = 'a'.repeat(64);
let sent: { path: string; body: unknown }[] = [];
let fail = false;

function list() {
  return {
    items_by_status: { needs_context: 1 },
    awaiting_admission: [{ id: itemId, source: 'whatsapp', external_id: 'w1', title: 'Nuevo reporte', text: 'Implementar el reporte mensual',
      status: 'needs_context', url: null, occurred_at: '2026-10-27T12:00:00Z',
      admission: { decision: 'ask_context', decided_by: 'policy', reasons: ['no registered project matches this request'], project: null, profile: null, role: null } }],
    jobs: [{ id: jobId, key: 'fj-1', item_id: itemId, project: 'landing', status: 'queued', attempts: 0, error_code: null, risk: null,
      requires_human: null, human_reasons: [], branch: null, checks: [], review: null }],
    pending_effects: [{ id: effectId, job_id: jobId, kind: 'open_pr', policy: 'human', state: 'proposed', payload: { branch: 'factory/fj-1-a1', title: 'Botón verde' },
      fingerprint, expires_at: '2026-10-28T12:00:00Z', decided_by: null, result: null }],
    projects: [{ name: 'landing', profile: 'frontend' }, { name: 'etl-lambdas', profile: 'lambdas' }],
  };
}

beforeEach(() => {
  sent = []; fail = false;
  vi.stubGlobal('confirm', vi.fn(() => true));
  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (input, init) => {
    const path = String(input);
    if (path.endsWith('/session')) return new Response(JSON.stringify({ token: 'synthetic-token' }));
    if (path.endsWith('/factory/list')) return new Response(JSON.stringify(list()));
    if (path.includes('/factory/')) {
      sent.push({ path, body: JSON.parse(String(init?.body)) });
      return new Response('{}', { status: fail ? 409 : 200 });
    }
    throw new Error('Unexpected capability: ' + path);
  }));
});
afterEach(() => vi.unstubAllGlobals());

describe('Fábrica', () => {
  it('muestra lo que espera decisión, los trabajos y las acciones con su contenido exacto', async () => {
    render(<FactoryWorkspace />);
    expect(await screen.findByText('Nuevo reporte')).toBeInTheDocument();
    expect(screen.getByText('no registered project matches this request')).toBeVisible();
    expect(screen.getByText('Abrir merge request')).toBeVisible();
    expect(screen.getByText(/factory\/fj-1-a1/)).toBeVisible();
    expect(screen.getByText('En cola')).toBeVisible();
    expect(sent).toEqual([]);
  });

  it('no aprueba nada sin confirmación y envía el fingerprint exacto al aprobar', async () => {
    render(<FactoryWorkspace />);
    const approve = await screen.findByRole('button', { name: 'Aprobar esta acción' });
    vi.mocked(confirm).mockReturnValueOnce(false);
    fireEvent.click(approve);
    expect(sent).toEqual([]);
    fireEvent.click(approve);
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0].path).toContain('/factory/effect');
    expect(sent[0].body).toEqual({ id: effectId, action: 'approve', fingerprint });
  });

  it('admite en el proyecto elegido y avisa si el servidor no confirmó la acción', async () => {
    render(<FactoryWorkspace />);
    await screen.findByText('Nuevo reporte');
    fireEvent.change(screen.getByLabelText('Proyecto'), { target: { value: 'etl-lambdas' } });
    fail = true;
    fireEvent.click(screen.getByRole('button', { name: 'Admitir' }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0].body).toEqual({ id: itemId, action: 'admit', project: 'etl-lambdas' });
    expect(await screen.findByRole('alert')).toHaveTextContent('No se confirmó la acción');
  });

  it('reorienta un trabajo con el texto literal del dueño', async () => {
    render(<FactoryWorkspace />);
    fireEvent.change(await screen.findByLabelText('Nuevo enfoque'), { target: { value: 'Mejor en azul' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reorientar' }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0].body).toEqual({ id: jobId, action: 'redirect', text: 'Mejor en azul' });
  });
});
