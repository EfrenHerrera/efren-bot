import { useEffect, useRef, useState } from 'react';
import { collectionRequest } from '@/collection-client';
import { factoryList } from '@/factory-client';
import type { FactoryList } from '@/factory-client';

export function useFactory() {
  const [data, setData] = useState<FactoryList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const alive = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const next = factoryList.parse(await collectionRequest('factory/list', 'POST', controller.signal, {}));
        if (!controller.signal.aborted) { setData(next); setError(null); }
      } catch { if (!controller.signal.aborted) setError('No se pudo actualizar la fábrica. Las decisiones están bloqueadas hasta recuperar el estado actual.'); }
      finally { if (!controller.signal.aborted) timer = setTimeout(() => { void load(); }, 4000); }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [version]);
  async function send(operation: string, body: Record<string, unknown>) {
    if (busy || error) return false;
    setBusy(true);
    try { await collectionRequest(`factory/${operation}`, 'POST', undefined, body); if (alive.current) setError(null); return true; }
    catch { if (alive.current) setError('No se confirmó la acción: cambió el estado o ya no está permitida. Actualiza antes de reintentar.'); return false; }
    finally { if (alive.current) { setBusy(false); setVersion(value => value + 1); } }
  }
  return { data, error, busy, refresh: () => setVersion(value => value + 1),
    admit: (id: string, project?: string) => send('admission', { id, action: 'admit', ...(project ? { project } : {}) }),
    discard: (id: string) => send('admission', { id, action: 'discard' }),
    control: (id: string, action: 'pause' | 'continue' | 'stop' | 'redirect', text = '') => send('control', { id, action, text }),
    decide: (id: string, action: 'approve' | 'deny', fingerprint: string) => send('effect', { id, action, fingerprint }) };
}
