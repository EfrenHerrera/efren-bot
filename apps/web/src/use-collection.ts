import { useCallback, useEffect, useRef, useState } from 'react';
import { collectionRequest, collectionSchema } from '@/collection-client';
import type { Collection, CollectionAction } from '@/collection-client';

const POLL_MS = 5000;

export function useCollection() {
  const [data, setData] = useState<Collection | null>(null);
  const [error, setError] = useState(false);
  const [pending, setPending] = useState(false);
  const mounted = useRef(false);
  const sequence = useRef(0);
  const current = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    const version = ++sequence.current;
    current.current?.abort();
    const controller = new AbortController();
    current.current = controller;
    try {
      const next = collectionSchema.parse(await collectionRequest('status', 'GET', controller.signal));
      if (mounted.current && sequence.current === version) { setData(next); setError(false); }
    } catch {
      if (mounted.current && !controller.signal.aborted && sequence.current === version) setError(true);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, POLL_MS);
    return () => { mounted.current = false; current.current?.abort(); window.clearInterval(timer); };
  }, [refresh]);

  async function command(action: CollectionAction) {
    if (pending) return;
    setPending(true);
    current.current?.abort();
    ++sequence.current;
    try {
      await collectionRequest(action, 'POST');
      await refresh();
    } catch { if (mounted.current) setError(true); }
    finally { if (mounted.current) setPending(false); }
  }
  return { data, error, pending, command, refresh };
}
