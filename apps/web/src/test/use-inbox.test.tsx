import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useInbox } from '@/use-inbox';

const timestamp = '2026-10-25T23:00:00Z';
afterEach(() => vi.unstubAllGlobals());

describe('Paginación de la bandeja', () => {
  it('conserva instantánea al paginar y la renueva cuando llegan registros', async () => {
    const bodies: Array<{ offset: number; snapshot_at: string | null }> = [];
    vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (input, init) => {
      if (String(input).endsWith('/session')) return new Response(JSON.stringify({ token: 'synthetic-token' }));
      const body = JSON.parse(String(init?.body));
      bodies.push(body);
      return new Response(JSON.stringify({ messages: [], total: 100, offset: body.offset, snapshot_at: timestamp, next_offset: body.offset === 0 ? 50 : null, channels: [] }));
    }));
    const hook = renderHook(({ count }) => useInbox(count), { initialProps: { count: 0 } });
    await waitFor(() => expect(hook.result.current.data?.total).toBe(100));
    act(() => hook.result.current.setOffset(50));
    await waitFor(() => expect(hook.result.current.data?.offset).toBe(50));
    expect(bodies.at(-1)).toEqual(expect.objectContaining({ offset: 50, snapshot_at: timestamp }));
    hook.rerender({ count: 1 });
    await waitFor(() => expect(hook.result.current.data?.offset).toBe(0));
    expect(bodies.at(-1)).toEqual(expect.objectContaining({ offset: 0, snapshot_at: null }));
    hook.unmount();
  });

  it('aborta la lectura pendiente al desmontar', async () => {
    let signal: AbortSignal | null | undefined;
    vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (input, init) => {
      if (String(input).endsWith('/session')) return new Response(JSON.stringify({ token: 'synthetic-token' }));
      signal = init?.signal;
      return new Promise<Response>(() => {});
    }));
    const hook = renderHook(() => useInbox(0));
    await waitFor(() => expect(signal).toBeDefined());
    hook.unmount();
    expect(signal?.aborted).toBe(true);
  });
});
