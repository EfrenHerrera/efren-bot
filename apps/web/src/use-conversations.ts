import { useCallback, useEffect, useRef, useState } from 'react';
import { collectionRequest } from '@/collection-client';
import { conversationDetailSchema, conversationKey, conversationListSchema } from '@/conversation-client';
import type { Conversation, ConversationDetail, ConversationFilters, Group, GroupDraft } from '@/conversation-client';
import type { z } from 'zod';

const PAGE_SIZE = 50;

export function useConversations(messageCount: number, preserveSelection = false) {
  const [data, setData] = useState<z.infer<typeof conversationListSchema> | null>(null);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [filters, setFilters] = useState<ConversationFilters>({ view: 'all', query: '', channel_id: '', category: '', attention: '' });
  const [offset, setOffset] = useState(0);
  const [contextOffset, setContextOffset] = useState(0);
  const [listVersion, setListVersion] = useState(0);
  const [detailVersion, setDetailVersion] = useState(0);
  const [loading, setLoading] = useState(false);
  const [contextLoading, setContextLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listSnapshot = useRef<string | null>(null);
  const detailSnapshot = useRef<string | null>(null);
  const alive = useRef(false);
  const mutation = useRef<AbortController | null>(null);
  const pinned = useRef(preserveSelection); pinned.current = preserveSelection;
  const selectionKey = selected ? conversationKey(selected) : null;

  useEffect(() => { alive.current = true; return () => { alive.current = false; mutation.current?.abort(); }; }, []);
  useEffect(() => { listSnapshot.current = null; setOffset(0); }, [messageCount]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      void collectionRequest('conversations/list', 'POST', controller.signal, { ...filters, category: filters.category || null, attention: filters.attention || null, offset, snapshot_at: listSnapshot.current }).then(raw => {
        const next = conversationListSchema.parse(raw);
        if (controller.signal.aborted || !alive.current) return;
        setData(next); listSnapshot.current = next.snapshot_at;
        setSelected(previous => next.conversations.find(row => previous && conversationKey(row) === conversationKey(previous)) || (pinned.current && previous ? previous : next.conversations[0] || null));
        setError(null);
      }).catch(() => { if (alive.current && !controller.signal.aborted) setError('No se pudieron cargar las conversaciones.'); })
        .finally(() => { if (alive.current && !controller.signal.aborted) setLoading(false); });
    }, 180);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [filters, offset, listVersion, messageCount]);

  useEffect(() => { detailSnapshot.current = null; setContextOffset(0); setDetail(null); }, [selectionKey]);
  useEffect(() => {
    if (!selected) { setDetail(null); return; }
    const controller = new AbortController();
    setContextLoading(true);
    void collectionRequest('conversations/detail', 'POST', controller.signal, { id: selected.id, offset: contextOffset, snapshot_at: detailSnapshot.current }).then(raw => {
      const next = conversationDetailSchema.parse(raw);
      if (controller.signal.aborted || !alive.current) return;
      detailSnapshot.current = next.snapshot_at; setDetail(next); setError(null);
    }).catch(() => { if (alive.current && !controller.signal.aborted) setError('No se pudo cargar el contexto de esta conversación.'); })
      .finally(() => { if (alive.current && !controller.signal.aborted) setContextLoading(false); });
    return () => controller.abort();
  }, [selected?.id, selectionKey, contextOffset, detailVersion]);

  function changeFilters(next: ConversationFilters) { listSnapshot.current = null; setOffset(0); setFilters(next); }
  const refresh = useCallback(() => { listSnapshot.current = null; detailSnapshot.current = null; setListVersion(value => value + 1); setDetailVersion(value => value + 1); }, []);
  function choose(value: Conversation) { setSelected(value); if (selected && conversationKey(selected) === conversationKey(value)) { detailSnapshot.current = null; setDetailVersion(previous => previous + 1); } }
  async function perform(path: string, body: unknown) {
    if (mutation.current) return false;
    const controller = new AbortController(); mutation.current = controller; setSaving(true); setError(null);
    try {
      await collectionRequest(path, 'POST', controller.signal, body);
      if (alive.current && !controller.signal.aborted) refresh();
      return true;
    } catch (cause) {
      if (alive.current && !controller.signal.aborted) setError(cause instanceof Error && cause.message === 'collection_conflict' ? 'El asunto cambió o esta solicitud ya se usó. Actualiza el contexto antes de volver a guardar.' : 'No se confirmó el cambio. Tu borrador se conserva; vuelve a intentar.');
      return false;
    } finally { mutation.current = null; if (alive.current) setSaving(false); }
  }
  async function saveGroup(draft: GroupDraft) { return selected ? perform('conversations/group-save', { ...draft, conversation_message_id: selected.id }) : false; }
  async function removeGroup(group: Group) {
    if (!window.confirm(`¿Quitar «${group.title}» del seguimiento? Los mensajes se conservan.`)) return;
    await perform('conversations/group-delete', { id: group.id, revision: group.revision });
  }
  async function markSeen() { if (selected && detail) await perform('conversations/seen', { id: selected.id, snapshot_at: detail.snapshot_at }); }
  return { data, selected, detail, filters, changeFilters, choose, loading, contextLoading, saving, error, refresh, offset, setOffset, contextOffset, setContextOffset, previousContext: () => setContextOffset(value => Math.max(0, value - PAGE_SIZE)), saveGroup, removeGroup, markSeen };
}
