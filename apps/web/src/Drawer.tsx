import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

export function Drawer({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  const onClose = useRef(close); onClose.current = close;
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement;
    if (dialog && !dialog.open) dialog.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { dialog?.close(); document.body.style.overflow = overflow; if (previous instanceof HTMLElement) previous.focus(); };
  }, []);
  return <dialog ref={ref} className="drawer" aria-labelledby="drawer-title" onCancel={event => { event.preventDefault(); onClose.current(); }}>
    <header className="drawer-heading"><h2 id="drawer-title">{title}</h2><button type="button" className="icon-button" aria-label="Cerrar panel" onClick={close}>×</button></header>
    <div className="drawer-body">{children}</div>
  </dialog>;
}
