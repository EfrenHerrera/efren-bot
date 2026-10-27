import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HumanWorkspace } from '@/HumanWorkspace';
import type { HumanDraft } from '@/human-client';

const id = '123e4567-e89b-42d3-a456-426614174000';
const second = '123e4567-e89b-42d3-a456-426614174001';
const at = '2026-10-26T06:00:00Z';
const proposal = { id, kind: 'gitlab_comment', label: 'Publicar este comentario', body: 'Exact private body', destination: 'https://gitlab.com/approved/synthetic/-/merge_requests/1', version: 2, enabled: true, reason: 'Versión vigente', fingerprint: 'a'.repeat(64), denied: false, expires_in_seconds: 900, position: { path: 'core/example.py', line: 2 }, refs: { head_sha: 'b'.repeat(40), base_sha: 'c'.repeat(40), start_sha: 'd'.repeat(40) } };
let revision = 1;
let blocked = false;
let fail = false;
let decisions: unknown[] = [];

function item() {
  return { domain: 'review', id, title: 'Synthetic MR', status: 'ready', revision, control_revision: 0,
    disposition: 'active', category: 'decision', conclusion: 'Saved **conclusion**', report_revision: 1,
    pending: ['Runtime not executed'], actions: [{ ...proposal, enabled: !blocked }], updated_at: at, error_code: null };
}

beforeEach(() => {
  revision = 1; blocked = false; fail = false; decisions = [];
  vi.stubGlobal('confirm', vi.fn(() => false));
  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (input, init) => {
    const path = String(input);
    if (path.endsWith('/session')) return new Response(JSON.stringify({ token: 'synthetic-token' }));
    if (path.endsWith('/human/list')) return new Response(JSON.stringify({
      items: [item(), { ...item(), id: second, title: 'Delegated MR', disposition: 'delegated', category: 'inactive', actions: [] }],
      controls: { support: { activated_at: at, paused: false, available: false, queued: 0 }, review: { activated_at: at, paused: true, available: false, queued: 2 } },
      capabilities: [{ kind: 'run_tests', label: 'Ejecutar pruebas', enabled: false, reason: 'Sin ejecutor autorizado' }], limit_per_domain: 100,
    }));
    if (path.endsWith('/human/detail')) return new Response(JSON.stringify({ request: item(), history: [], report: {}, snapshot: {} }));
    if (path.endsWith('/human/act')) {
      decisions.push(JSON.parse(String(init?.body)));
      return new Response('{}', { status: fail ? 409 : 200 });
    }
    throw new Error('Unexpected capability: ' + path);
  }));
});
afterEach(() => vi.unstubAllGlobals());

describe('Control humano común sin arrancar procesos', () => {
  it('separa disponibilidad y pausa y deja las capacidades inexistentes bloqueadas', async () => {
    render(<HumanWorkspace />);
    expect(await screen.findByRole('heading', { name: 'Synthetic MR' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Delegated MR/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Ejecutores y capacidades'));
    expect(screen.getAllByText('Sin ejecutor confirmado')).toHaveLength(2);
    expect(screen.getByText('Control pausado · 2 en cola')).toBeVisible();
    expect(screen.getByText('Sin ejecutor autorizado')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Delegadas / pausadas' }));
    expect(await screen.findByRole('button', { name: /Delegated MR/ })).toBeInTheDocument();
    expect(decisions).toEqual([]);
  });
  it('exige confirmación del contenido, destino y versión concretos', async () => {
    render(<HumanWorkspace />);
    const approve = await screen.findByRole('button', { name: 'Autorizar esta acción' });
    fireEvent.click(approve);
    expect(decisions).toEqual([]);
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining(proposal.destination));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining(proposal.body));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('Versión: 2'));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('core/example.py:2'));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining(proposal.refs.head_sha));
    vi.stubGlobal('confirm', vi.fn(() => true));
    fireEvent.click(approve);
    await waitFor(() => expect(decisions).toEqual([expect.objectContaining({ action: 'approve', id, revision: 1, control_revision: 0, proposal_id: id, fingerprint: proposal.fingerprint })]));
  });
  it('no deja aprobar una capacidad bloqueada aunque conserve su borrador', async () => {
    blocked = true;
    render(<HumanWorkspace />);
    expect(await screen.findByRole('button', { name: 'Autorizar esta acción' })).toBeDisabled();
    fireEvent.click(screen.getByText('Revisar contenido exacto'));
    expect(screen.getByText(proposal.body)).toBeVisible();
    expect(decisions).toEqual([]);
  });
  it('preserva indicaciones entre pestañas y exige revalidarlas si cambia la versión', async () => {
    const drafts = new Map<string, HumanDraft>();
    const view = render(<HumanWorkspace drafts={drafts} />);
    await screen.findByRole('heading', { name: 'Synthetic MR' });
    fireEvent.click(screen.getByText('Dar contexto o cambiar el enfoque'));
    fireEvent.change(screen.getByRole('textbox', { name: 'Tu indicación' }), { target: { value: 'Keep this direction' } });
    view.unmount();
    revision = 2;
    render(<HumanWorkspace drafts={drafts} />);
    await screen.findByRole('heading', { name: 'Synthetic MR' });
    fireEvent.click(screen.getByText('Dar contexto o cambiar el enfoque'));
    expect(screen.getByRole('textbox', { name: 'Tu indicación' })).toHaveValue('Keep this direction');
    expect(screen.getByRole('button', { name: 'Guardar nuevo enfoque' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Usar mi texto en esta versión' }));
    fail = true;
    fireEvent.click(screen.getByRole('button', { name: 'Guardar nuevo enfoque' }));
    await waitFor(() => expect(decisions).toEqual([expect.objectContaining({ action: 'redirect', revision: 2, text: 'Keep this direction' })]));
    expect(screen.getByRole('textbox', { name: 'Tu indicación' })).toHaveValue('Keep this direction');
  });
  it('delegar requiere confirmación y no significa resolver la MR', async () => {
    render(<HumanWorkspace />);
    const delegate = await screen.findByRole('button', { name: 'Delegar' });
    fireEvent.click(delegate);
    expect(decisions).toEqual([]);
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('No significa que el problema esté resuelto'));
    vi.stubGlobal('confirm', vi.fn(() => true));
    fireEvent.click(delegate);
    await waitFor(() => expect(decisions).toEqual([expect.objectContaining({ action: 'delegate' })]));
  });
});
