import { useEffect, useRef, useState } from 'react';
import { collectionRequest } from '@/collection-client';
import { reviewDetail, reviewList } from '@/review-client';
import type { Proposal, ReviewAction, ReviewDetail, ReviewList } from '@/review-client';

const POLL_MS = 4000;

export function useReviews(targetId?: string) {
  const [data, setData] = useState<ReviewList | null>(null);
  const [detail, setDetail] = useState<ReviewDetail | null>(null);
  const [selection, setSelected] = useState<string | null>(null);
  const selected = targetId || selection;
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const alive = useRef(false);
  const mutation = useRef<AbortController | null>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; mutation.current?.abort(); }; }, []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const next = reviewList.parse(await collectionRequest('reviews/list', 'POST', controller.signal, {}));
        if (controller.signal.aborted) return;
        setData(next); if (!targetId) setSelected(previous => previous && next.items.some(item => item.id === previous) ? previous : next.items[0]?.id || null);
        if (selected) {
          const detail = reviewDetail.parse(await collectionRequest('reviews/detail', 'POST', controller.signal, { id: selected }));
          if (!controller.signal.aborted) setDetail(detail);
        }
        if (!controller.signal.aborted) setError(null);
      } catch { if (!controller.signal.aborted) setError('No se pudo actualizar la revisión. El último avance puede estar desactualizado.'); }
      finally { if (!controller.signal.aborted) timer = setTimeout(() => { void load(); }, POLL_MS); }
    }
    setDetail(previous => previous?.item.id === selected ? previous : null);
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [selected, targetId, version]);
  async function command(path: string, body: unknown) {
    if (mutation.current) return false;
    const controller = new AbortController(); mutation.current = controller; setBusy(true);
    try {
      await collectionRequest(`reviews/${path}`, 'POST', controller.signal, body);
      if (!controller.signal.aborted && alive.current) { setVersion(value => value + 1); setError(null); }
      return true;
    } catch (cause) {
      if (!controller.signal.aborted && alive.current) setError(cause instanceof Error && cause.message === 'collection_conflict' ? 'La revisión o propuesta cambió, o la acción no está permitida. Actualiza antes de decidir; tu texto se conserva.' : 'No se confirmó la acción. El texto se conserva para reintentar.');
      return false;
    } finally { mutation.current = null; if (alive.current) setBusy(false); }
  }
  function act(action: ReviewAction, text: string, key: string, proposal?: Proposal) {
    return detail ? command('act', { id: detail.item.id, revision: detail.item.revision, action, text, request_id: key, proposal_id: proposal?.id || null, proposal_version: proposal?.version || null }) : Promise.resolve(false);
  }
  return { data, detail, selected, setSelected, error, busy, command, act, refresh: () => setVersion(value => value + 1) };
}
