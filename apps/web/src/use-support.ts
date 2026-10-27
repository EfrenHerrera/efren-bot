import { useEffect, useRef, useState } from 'react';
import { collectionRequest } from '@/collection-client';
import { supportDetail, supportList } from '@/support-client';
import type { SupportAction, SupportDetail, SupportList } from '@/support-client';

const POLL_MS = 4000;

export function useSupport() {
  const [data, setData] = useState<SupportList | null>(null);
  const [detail, setDetail] = useState<SupportDetail | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
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
        const next = supportList.parse(await collectionRequest('support/list', 'POST', controller.signal, {}));
        if (controller.signal.aborted) return;
        setData(next);
        setSelected(previous => previous && next.cases.some(item => item.id === previous) ? previous : next.cases[0]?.id || null);
        if (selected) {
          const context = supportDetail.parse(await collectionRequest('support/detail', 'POST', controller.signal, { id: selected }));
          if (!controller.signal.aborted) setDetail(context);
        }
        if (!controller.signal.aborted) setError(null);
      } catch { if (!controller.signal.aborted) setError('No se pudo actualizar soporte. El último avance puede estar desactualizado.'); }
      finally { if (!controller.signal.aborted) timer = setTimeout(() => { void load(); }, POLL_MS); }
    }
    setDetail(previous => previous?.case.id === selected ? previous : null);
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [selected, version]);
  async function command(path: string, body: unknown) {
    if (mutation.current) return false;
    const controller = new AbortController(); mutation.current = controller; setBusy(true);
    try {
      await collectionRequest(`support/${path}`, 'POST', controller.signal, body);
      if (!controller.signal.aborted && alive.current) { setVersion(value => value + 1); setError(null); }
      return true;
    } catch {
      if (!controller.signal.aborted && alive.current) setError('No se confirmó la acción. El mensaje se conserva para reintentar.');
      return false;
    } finally { mutation.current = null; if (alive.current) setBusy(false); }
  }
  function act(action: SupportAction, text: string, requestId: string) {
    return selected ? command('act', { id: selected, action, text, request_id: requestId }) : Promise.resolve(false);
  }
  return { data, detail, selected, setSelected, error, busy, act, command };
}
