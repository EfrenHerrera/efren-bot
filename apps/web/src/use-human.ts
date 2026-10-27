import { useEffect, useRef, useState } from 'react';
import { collectionRequest } from '@/collection-client';
import { humanDetail, humanList, matches, requestKey } from '@/human-client';
import type { HumanAction, HumanChoice, HumanDetail, HumanDraft, HumanFilter, HumanList } from '@/human-client';

export function useHuman(filter: HumanFilter) {
  const [data, setData] = useState<HumanList | null>(null);
  const [detail, setDetail] = useState<HumanDetail | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const mutation = useRef<AbortController | null>(null);
  const alive = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; mutation.current?.abort(); }; }, []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const next = humanList.parse(await collectionRequest('human/list', 'POST', controller.signal, {}));
        if (controller.signal.aborted) return;
        setData(next);
        const visible = next.items.filter(item => matches(item, filter));
        setSelected(previous => visible.some(item => requestKey(item) === previous) ? previous : visible[0] ? requestKey(visible[0]) : null);
        const current = next.items.find(item => requestKey(item) === selected);
        if (current) {
          const nextDetail = humanDetail.parse(await collectionRequest('human/detail', 'POST', controller.signal, { id: current.id, domain: current.domain }));
          if (!controller.signal.aborted) setDetail(nextDetail);
        }
        if (!controller.signal.aborted) setError(null);
      } catch { if (!controller.signal.aborted) setError('No se pudo actualizar. Las decisiones están bloqueadas hasta recuperar el estado actual.'); }
      finally { if (!controller.signal.aborted) timer = setTimeout(() => { void load(); }, 4000); }
    }
    setDetail(previous => previous && requestKey(previous.request) === selected ? previous : null);
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [filter, selected, version]);
  async function act(choice: HumanChoice, draft?: HumanDraft, action?: HumanAction) {
    if (!detail || mutation.current || error) return false;
    const controller = new AbortController(); mutation.current = controller; setBusy(true);
    const item = detail.request;
    try {
      await collectionRequest('human/act', 'POST', controller.signal, { domain: item.domain, id: item.id,
        request_id: draft?.request_id || crypto.randomUUID(), revision: draft?.revision ?? item.revision,
        control_revision: draft?.control_revision ?? item.control_revision,
        action: choice, text: draft?.text || '', proposal_id: action?.id || null, fingerprint: action?.fingerprint || null });
      if (!controller.signal.aborted && alive.current) { setVersion(value => value + 1); setError(null); }
      return true;
    } catch {
      if (!controller.signal.aborted && alive.current) { setError('No se confirmó la decisión: cambió la versión o la acción no está permitida. Tu texto se conserva. Actualiza antes de reintentar.'); setVersion(value => value + 1); }
      return false;
    } finally { mutation.current = null; if (alive.current) setBusy(false); }
  }
  return { data, detail, selected, setSelected, error, busy, act, refresh: () => setVersion(value => value + 1) };
}
