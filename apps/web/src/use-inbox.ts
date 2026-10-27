import { useCallback, useEffect, useRef, useState } from 'react';
import { collectionRequest, inboxSchema, sourcesSchema, threadSchema, variantsSchema } from '@/collection-client';
import type { Attention, Category, Filters, Inbox, Source, Sources } from '@/collection-client';

export function useInbox(messageCount: number, enabled = true) {
  const [filters, setFilters] = useState<Filters>({ channel_id: '', query: '', review: 'all', origin: 'all', category: '', attention: '' });
  const [data, setData] = useState<Inbox | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);
  const [mutating, setMutating] = useState(false);
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const snapshot = useRef<string | null>(null);
  const alive = useRef(false);
  const mutation = useRef(false);
  const abort = useRef<AbortController | null>(null);
  const [sources, setSources] = useState<Sources | null>(null);
  const [detail, setDetail] = useState<ReturnType<typeof threadSchema.parse> | null>(null);
  const [variants, setVariants] = useState<ReturnType<typeof variantsSchema.parse> | null>(null);

  useEffect(() => { alive.current = true; return () => { alive.current = false; abort.current?.abort(); }; }, []);
  useEffect(() => { snapshot.current = null; setOffset(0); }, [messageCount]);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setFetching(true);
      const payload = { ...filters, category: filters.category || null, attention: filters.attention || null, offset, snapshot_at: snapshot.current };
      void collectionRequest('inbox/list', 'POST', controller.signal, payload).then(value => {
        const next = inboxSchema.parse(value);
        if (!controller.signal.aborted && alive.current) { setData(next); snapshot.current = next.snapshot_at; setError(null); }
      }).catch(() => { if (!controller.signal.aborted && alive.current) setError('No se pudo cargar la bandeja. Vuelve a intentar.'); })
        .finally(() => { if (!controller.signal.aborted && alive.current) setFetching(false); });
    }, 180);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [filters, offset, version, messageCount, enabled]);

  function changeFilters(next: Filters) { snapshot.current = null; setOffset(0); setFilters(next); }
  const refresh = useCallback(() => { snapshot.current = null; setVersion(value => value + 1); }, []);

  async function perform(work: (signal: AbortSignal) => Promise<void>) {
    if (mutation.current) return;
    mutation.current = true; setMutating(true); setError(null);
    const controller = new AbortController(); abort.current = controller;
    try { await work(controller.signal); }
    catch { if (alive.current && !controller.signal.aborted) setError('No se pudo completar el cambio. No se ha confirmado el guardado.'); }
    finally { mutation.current = false; if (alive.current) setMutating(false); }
  }

  async function annotate(id: string, patch: { reviewed?: boolean; category?: Category; attention?: Attention }) {
    await perform(async signal => { await collectionRequest('inbox/annotate', 'POST', signal, { id, ...patch }); if (alive.current) refresh(); });
  }
  async function loadSources() {
    setSources(null);
    await perform(async signal => { const next = sourcesSchema.parse(await collectionRequest('sources/list', 'POST', signal)); if (alive.current) setSources(next); });
  }
  async function saveSource(channel: Source, mode: Source['mode']) {
    await perform(async signal => {
      await collectionRequest('sources/save', 'POST', signal, { channel_id: channel.channel_id, mode });
      const next = sourcesSchema.parse(await collectionRequest('sources/list', 'POST', signal));
      if (alive.current) setSources(next);
    });
  }
  async function loadDetail(id: string, nextOffset = 0) {
    if (nextOffset === 0) setDetail(null);
    await perform(async signal => {
      const next = threadSchema.parse(await collectionRequest('inbox/thread', 'POST', signal, { id, offset: nextOffset }));
      if (alive.current) setDetail(previous => nextOffset > 0 && previous ? { ...next, messages: [...previous.messages, ...next.messages] } : next);
    });
  }
  async function loadVariants(id: string, nextOffset = 0) {
    if (nextOffset === 0) setVariants(null);
    await perform(async signal => {
      const next = variantsSchema.parse(await collectionRequest('inbox/variants', 'POST', signal, { id, offset: nextOffset }));
      if (alive.current) setVariants(previous => nextOffset > 0 && previous ? { ...next, messages: [...previous.messages, ...next.messages] } : next);
    });
  }
  return { data, filters, changeFilters, error, busy: fetching || mutating, refresh, offset, setOffset, annotate, sources, loadSources, saveSource, detail, loadDetail, variants, loadVariants };
}
