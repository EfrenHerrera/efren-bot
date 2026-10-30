import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '@/App';

const timestamp = '2026-10-25T23:00:00Z';
const rootId = '123e4567-e89b-42d3-a456-426614174000';
const replyId = '123e4567-e89b-42d3-a456-426614174001';
const state = { activated_at: timestamp, paused: true, next_due_at: null, watermark: null, runner_seen_at: timestamp, runner_available: true, active_run: null, runs: [], messages: [], message_count: 0, interval_seconds: 900 };
const message = { id: rootId, source_scope: 'synthetic', channel_id: 'C1234567890', channel_name: 'synthetic-channel', message_id: 'root', thread_id: null, actor_id: 'synthetic-author', text: 'Synthetic root request <@U0B6T31KXSNX|Other person>', occurred_at: timestamp, observed_at: timestamp, source_url: null, historical: true, variant_count: 1, reviewed: false, reviewed_at: null, is_new: false, category: 'unclassified', attention: 'undecided', mentions_me: false, mention_excerpt: null };
const reply = { ...message, id: replyId, message_id: 'reply', thread_id: 'root', text: '<@U0B6T31KXSN> synthetic request in reply', mentions_me: true, mention_excerpt: '<@U0B6T31KXSN> synthetic request in reply' };
const conversation = { id: rootId, source_scope: 'synthetic', channel_id: message.channel_id, channel_name: message.channel_name, conversation_id: 'root', preview: message.text, root_present: true, relation_status: 'confirmed', message_count: 2, mention_count: 1, new_count: 0, group_count: 0, last_activity_at: timestamp, mention_previews: [{ id: replyId, excerpt: reply.text }] };
let groups: Array<{ id: string; title: string; category: string; attention: string; revision: number; message_ids: string[]; evidence_count: number; all_context: boolean }> = [];

beforeEach(() => {
  groups = [];
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open'); } });
  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (input, init) => {
    const path = String(input);
    let value: unknown = state;
    if (path.endsWith('/session')) value = { token: 'synthetic-token' };
    else if (path.endsWith('/conversations/list')) {
      const body = JSON.parse(String(init?.body));
      const visible = body.view !== 'new' && (body.view !== 'following' || groups.length > 0);
      value = { conversations: visible ? [{ ...conversation, group_count: groups.length }] : [], total: visible ? 1 : 0, snapshot_at: timestamp, offset: 0, next_offset: null, channels: [{ channel_id: message.channel_id, channel_name: message.channel_name }] };
    } else if (path.endsWith('/conversations/detail')) value = { self_user_id: 'U0B6T31KXSN', conversation: { ...conversation, group_count: groups.length, root: message }, groups, messages: [message, reply], total: 2, offset: 0, next_offset: null, snapshot_at: timestamp, mention_locations: [{ id: replyId, offset: 0, excerpt: reply.text }] };
    else if (path.endsWith('/conversations/group-save')) {
      const body = JSON.parse(String(init?.body));
      groups.push({ id: crypto.randomUUID(), title: body.title, category: body.category, attention: body.attention, revision: 1, message_ids: body.message_ids, evidence_count: body.message_ids.length, all_context: body.message_ids.length === 0 });
      value = { id: groups.at(-1)?.id, revision: 1 };
    } else if (path.endsWith('/sources/list')) value = { observed_at: timestamp, channels: [{ channel_id: message.channel_id, channel_name: message.channel_name, available: true, mode: 'mentions', since: null }] };
    return new Response(JSON.stringify(value));
  }));
});
afterEach(() => vi.unstubAllGlobals());

describe('Conversaciones con contexto y seguimiento opcional', () => {
  it('ofrece solo fuentes, solicitudes y ejecución como navegación principal', () => {
    render(<App />);
    const nav = screen.getByRole('navigation', { name: 'Área de trabajo' });
    expect(within(nav).getAllByRole('button').map(button => button.textContent)).toEqual(['Conversaciones', 'Solicitudes', 'Fábrica']);
  });
  it('agrupa respuestas y muestra contexto por defecto sin clasificación por comentario', async () => {
    const view = render(<App />);
    const context = screen.getByRole('region', { name: 'Contexto de la conversación' });
    expect(await within(context).findByText(/Synthetic root request/)).toBeInTheDocument();
    expect(within(context).getByText('@Other person')).toBeInTheDocument();
    expect(await within(context).findByText(/synthetic request in reply/)).toBeInTheDocument();
    expect(view.container.querySelectorAll('.conversation-choice')).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'Marcar revisado' })).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Clasificación del mensaje' })).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalledWith('/api/collection/inbox/list', expect.anything());
  });
  it('detecta una mención dentro de la respuesta y permite localizarla', async () => {
    render(<App />);
    expect(await screen.findByText('Te mencionan en 1 mensaje del contexto')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Ir a mención 1' }));
    expect(screen.getByText('Tú')).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalledWith('/api/collection/conversations/seen', expect.anything());
  });
  it('organiza tres asuntos manuales sin convertir cada respuesta en tarea', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Organizar un asunto' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Qué quieres seguir' }), { target: { value: 'First subject' } });
    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    fireEvent.click(screen.getByRole('button', { name: 'Guardar asunto' }));
    await screen.findByText('First subject');
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/collection/conversations/group-save', expect.objectContaining({ body: expect.stringContaining(replyId) })));
    for (const title of ['Second subject', 'Third subject']) {
      fireEvent.click(await screen.findByRole('button', { name: 'Añadir otro asunto' }));
      fireEvent.change(screen.getByRole('textbox', { name: 'Qué quieres seguir' }), { target: { value: title } });
      fireEvent.click(screen.getByRole('button', { name: 'Guardar asunto' }));
      await screen.findByText(title);
    }
    expect(groups).toHaveLength(3);
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalledWith('/api/collection/inbox/annotate', expect.anything());
  });
  it('conserva el borrador si el guardado falla', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Organizar un asunto' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Qué quieres seguir' }), { target: { value: 'Keep draft' } });
    const existing = fetch;
    vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (input, init) => String(input).endsWith('/group-save') ? new Response('{}', { status: 409 }) : existing(input, init)));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar asunto' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('El asunto cambió');
    expect(screen.getByRole('textbox', { name: 'Qué quieres seguir' })).toHaveValue('Keep draft');
  });
  it('mantiene la actividad de recolección en un panel secundario con retorno de foco', async () => {
    render(<App />);
    const button = screen.getByRole('button', { name: 'Actividad de recolección' }); button.focus(); fireEvent.click(button);
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar panel' }));
    expect(button).toHaveFocus();
    expect(screen.queryByText('Últimas ejecuciones')).not.toBeInTheDocument();
  });
  it('permite recolectar mientras está pausado y configurar fuentes', async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Recolectar ahora' }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/collection/run', expect.objectContaining({ method: 'POST' })));
    fireEvent.click(await screen.findByRole('button', { name: 'Configurar fuentes' }));
    const dialog = await screen.findByRole('dialog');
    const select = await within(dialog).findByRole('combobox', { name: `Modo de ${message.channel_name}` });
    fireEvent.change(select, { target: { value: 'full' } }); fireEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/collection/sources/save', expect.objectContaining({ body: JSON.stringify({ channel_id: message.channel_id, mode: 'full' }) })));
  });
  it('no trata el histórico como actividad nueva ni crea seguimiento por abrir contexto', async () => {
    render(<App />);
    await screen.findByRole('button', { name: 'Organizar un asunto' });
    fireEvent.click(screen.getByRole('button', { name: 'Actividad nueva' }));
    expect(await screen.findByText(/No hay actividad nueva en esta vista/)).toBeInTheDocument();
    expect(groups).toHaveLength(0);
  });
});
