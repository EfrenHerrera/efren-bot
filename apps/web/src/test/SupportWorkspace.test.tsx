import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SupportWorkspace } from '@/SupportWorkspace';

const id = '123e4567-e89b-42d3-a456-426614174000';
const at = '2026-10-26T05:00:00Z';
const current = {
  id, anchor_id: id, title: 'Synthetic support case', status: 'blocked', revision: 2,
  context: { conversation_id: 'thread', channel_name: 'synthetic', trigger_id: id,
    root_present: false, relation_status: 'confirmed', truncated: false,
    messages: [{ id, text: 'Synthetic incident report', occurred_at: at }] },
  report: { reported: ['Reported error'], hypotheses: ['Unconfirmed possibility'], missing: ['Approved source scope'],
    evidence_ids: [id], slack_draft: 'Synthetic preliminary draft', coverage: 'slack_only', revision: 1 },
  error_code: 'source_scope_pending', created_at: at, updated_at: at,
};
let empty = false;
let fail = false;

beforeEach(() => {
  empty = false; fail = false;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (input) => {
    const path = String(input);
    let value: unknown = {};
    if (path.endsWith('/session')) value = { token: 'synthetic-support-token' };
    if (path.endsWith('/support/list')) value = { control: { activated_at: at, paused: false, runner_available: true },
      source_limits: { cloudwatch: 'Pending approval' }, cases: empty ? [] : [current], intakes: [] };
    if (path.endsWith('/support/detail')) value = { case: current, entries: [{ id, kind: 'classification',
      text: 'New incident', status: 'recorded', created_at: at }] };
    if (path.endsWith('/support/act') && fail) return new Response('{}', { status: 503 });
    return new Response(JSON.stringify(value));
  }));
});
afterEach(() => vi.unstubAllGlobals());

describe('Soporte supervisado sin falsas fuentes', () => {
  it('muestra bloqueo real, hipótesis y alcance; no inventa consultas completadas', async () => {
    render(<SupportWorkspace openConversation={() => {}} />);
    expect(await screen.findByText('Preliminar · solo lo reportado en Slack')).toBeInTheDocument();
    expect(screen.getByText(/No se han leído CloudWatch/)).toBeInTheDocument();
    expect(screen.getByText(/El preliminar anterior corresponde a la revisión 1/)).toBeInTheDocument();
    expect(screen.getByText('Hipótesis, no causas confirmadas')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Publicar/ })).not.toBeInTheDocument();
  });
  it('permite preguntar sin reiniciar y corregir el rumbo de forma explícita', async () => {
    render(<SupportWorkspace openConversation={() => {}} />);
    const field = await screen.findByRole('textbox', { name: 'Mensaje para esta investigación' });
    fireEvent.change(field, { target: { value: 'What did you find?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Preguntar' }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/collection/support/act', expect.objectContaining({ body: expect.stringContaining('"action":"ask"') })));
    await waitFor(() => expect(field).toHaveValue(''));
    fireEvent.change(field, { target: { value: 'Use a different timeframe' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar corrección' }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/collection/support/act', expect.objectContaining({ body: expect.stringContaining('"action":"redirect"') })));
  });
  it('conserva el mensaje y permite pausar soporte sin tocar el recolector', async () => {
    render(<SupportWorkspace openConversation={() => {}} />);
    const field = await screen.findByRole('textbox', { name: 'Mensaje para esta investigación' });
    fail = true;
    fireEvent.change(field, { target: { value: 'Keep this question' } });
    fireEvent.click(screen.getByRole('button', { name: 'Preguntar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('No se confirmó la acción');
    expect(field).toHaveValue('Keep this question');
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Pausar soporte' }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/collection/support/pause', expect.anything()));
    expect(fetch).not.toHaveBeenCalledWith('/api/collection/pause', expect.anything());
  });
  it('no presenta el histórico como trabajo iniciado', async () => {
    empty = true;
    render(<SupportWorkspace openConversation={() => {}} />);
    expect(await screen.findByText(/No hay casos nuevos. No se investigó el histórico/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Preguntar' })).not.toBeInTheDocument();
  });
});
