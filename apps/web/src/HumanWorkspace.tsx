import { useEffect, useRef, useState } from 'react';
import { choiceLabels, dispositionLabels, filterLabels, matches, requestKey } from '@/human-client';
import type { HumanAction, HumanChoice, HumanDetail, HumanDraft, HumanFilter, HumanRequest } from '@/human-client';
import { CodeBlock, ReviewText } from '@/ReviewText';
import { useHuman } from '@/use-human';
import '@/review.css';
import '@/human.css';

type Inbox = ReturnType<typeof useHuman>;
const filters: HumanFilter[] = ['decision', 'working', 'conclusion', 'inactive', 'all'];
const domains: HumanRequest['domain'][] = ['support', 'review'];
const dates = new Intl.DateTimeFormat('es-MX', { dateStyle: 'short', timeStyle: 'short' });

function DecisionPanel({ detail, inbox, drafts }: { detail: HumanDetail; inbox: Inbox; drafts: Map<string, HumanDraft> }) {
  const item = detail.request;
  const key = requestKey(item);
  const [draft, setDraft] = useState<HumanDraft>(() => drafts.get(key) || { text: '', revision: item.revision, control_revision: item.control_revision, request_id: crypto.randomUUID() });
  useEffect(() => { drafts.set(key, draft); }, [drafts, key, draft]);
  const disabled = inbox.busy || Boolean(inbox.error);
  const stale = Boolean(draft.text) && (draft.revision !== item.revision || draft.control_revision !== item.control_revision);
  async function control(choice: HumanChoice) {
    if (['ignore', 'delegate', 'stop'].includes(choice) && !window.confirm(`${choiceLabels[choice]}: ${item.title}\n\nSe detendrán nuevas operaciones. No significa que el problema esté resuelto ni deshace un envío ya admitido.`)) return;
    if (await inbox.act(choice, draft.text ? draft : undefined)) setDraft({ text: '', revision: item.revision, control_revision: item.control_revision, request_id: crypto.randomUUID() });
  }
  function decide(choice: 'approve' | 'deny', action: HumanAction) {
    const position = action.position ? `\nArchivo: ${action.position.path}:${action.position.line}` : '';
    const refs = action.refs ? `\nHead: ${action.refs.head_sha}\nBase: ${action.refs.base_sha}\nStart: ${action.refs.start_sha}` : '';
    if (!window.confirm(`${choice === 'approve' ? 'Autorizar y encolar SOLO esta acción' : 'Denegar esta acción'}\n\n${action.label}\nDestino: ${action.destination}\nVersión: ${action.version}${position}${refs}\n\n${action.body}\n\n${choice === 'approve' ? 'La autorización vence en 15 minutos y se revalida antes de enviar. No aprueba ni resuelve la MR.' : 'Se conserva el contenido y la decisión en el historial.'}`)) return;
    void inbox.act(choice, undefined, action);
  }
  return <section className="review-detail human-detail" aria-label="Solicitud seleccionada">
    <p className="eyebrow">{item.domain === 'support' ? 'Soporte' : 'Revisión de MR'} · Revisión {item.revision}</p><h3>{item.title}</h3>
    <div className="human-state" data-state={item.disposition}><strong>{dispositionLabels[item.disposition]}</strong><span>{item.disposition === 'delegated' ? 'La atiende otra persona; Efren Bot no continúa.' : item.disposition !== 'active' ? 'Sin nuevas operaciones hasta tu intervención.' : 'Solo dentro del alcance autorizado.'}</span></div>
    <section className="human-controls" aria-label="Control del seguimiento">
      <button className="primary-button" disabled={disabled || stale} onClick={() => { void control(item.disposition === 'active' ? 'continue' : 'attend'); }}>{item.disposition === 'active' ? 'Continuar / revalidar' : 'Atender de nuevo'}</button>
      <button className="secondary-button" disabled={disabled || stale || item.disposition === 'paused'} onClick={() => { void control('pause'); }}>Pausar</button>
      <button className="secondary-button" disabled={disabled || stale || item.disposition === 'delegated'} onClick={() => { void control('delegate'); }}>Delegar</button>
      <button className="text-button" disabled={disabled || stale || item.disposition === 'ignored'} onClick={() => { void control('ignore'); }}>No atender</button>
      <button className="text-button" disabled={disabled || stale || item.disposition === 'stopped'} onClick={() => { void control('stop'); }}>Detener</button>
    </section>
    <details className="human-direction"><summary>Dar contexto o cambiar el enfoque</summary>
      <label>Tu indicación<textarea maxLength={4000} value={draft.text} disabled={inbox.busy} onChange={event => setDraft(previous => ({ text: event.target.value, request_id: crypto.randomUUID(), revision: previous.text ? previous.revision : item.revision, control_revision: previous.text ? previous.control_revision : item.control_revision }))} /></label>
      {stale && <p role="status">La solicitud cambió mientras escribías. Tu texto se conserva. Revísalo antes de aplicarlo a la versión actual.<button className="text-button" onClick={() => setDraft(previous => ({ ...previous, revision: item.revision, control_revision: item.control_revision, request_id: crypto.randomUUID() }))}>Usar mi texto en esta versión</button></p>}
      <button className="secondary-button" disabled={disabled || stale || !draft.text.trim()} onClick={() => { void control('redirect'); }}>Guardar nuevo enfoque</button>
    </details>
    <section className="human-conclusion"><h4>Última conclusión guardada</h4>
      {item.conclusion ? <><p className="review-help">Revisión {item.report_revision}{item.report_revision !== item.revision ? ' · anterior al estado actual' : ''} · No equivale a resolución ni permiso de publicar.</p><ReviewText text={item.conclusion} /></> : <p className="review-help">Todavía no hay una conclusión. Estado técnico: {item.status}.</p>}
      {Boolean(item.pending.length) && <details><summary>Qué falta · {item.pending.length}</summary><ul>{item.pending.map(value => <li key={value}><ReviewText text={value} /></li>)}</ul></details>}
      {item.status === 'partial' && <p className="human-warning">Revisión parcial: faltan comprobaciones o evidencia.</p>}
      {item.error_code && <p className="human-warning">Bloqueo técnico: {item.error_code}</p>}
      <details><summary>Informe y evidencia guardados</summary><p className="review-help">Detalle técnico original de solo lectura; abrirlo no inicia otra investigación.</p><CodeBlock text={JSON.stringify(detail.report, null, 2)} language="json" label="Informe" /><CodeBlock text={JSON.stringify(detail.snapshot, null, 2)} language="json" label="Evidencia guardada" /></details>
    </section>
    <section aria-label="Acciones propuestas"><h4>Acciones importantes</h4><p className="review-help">Aprobar una acción no autoriza las siguientes ni crea una capacidad que aún no existe.</p>
      {!item.actions.length && <p className="human-empty">No hay acciones propuestas para esta versión.</p>}
      {item.actions.map(action => <article className="human-action" key={action.id}>
        <header><strong>{action.label}</strong><span>{action.denied ? 'Denegada' : action.enabled ? 'Necesita tu aprobación' : 'Bloqueada'}</span></header>
        <p className="human-destination">Destino: {action.destination} · Versión {action.version}</p>
        {action.position && <p className="human-destination">{action.position.path}:{action.position.line}</p>}
        <details><summary>Revisar contenido exacto</summary><ReviewText text={action.body} /></details>
        <p className="review-help">{action.reason}{action.expires_in_seconds ? ' Autorización limitada a 15 minutos.' : ''}</p>
        <div className="human-controls"><button className="primary-button" disabled={disabled || !action.enabled || action.denied} onClick={() => decide('approve', action)}>Autorizar esta acción</button><button className="secondary-button" disabled={disabled || action.denied} onClick={() => decide('deny', action)}>Denegar esta acción</button></div>
      </article>)}
    </section>
    <details className="human-history"><summary>Decisiones humanas · {detail.history.length}</summary>
      <ol>{detail.history.map(entry => <li key={entry.id}><strong>{Object.entries(choiceLabels).find(([choice]) => choice === entry.input.action)?.[1] || entry.input.action}</strong><time>{dates.format(new Date(entry.created_at))} · revisión {entry.input.revision}</time><ReviewText text={entry.input.text} /></li>)}</ol>
    </details>
  </section>;
}

export function HumanWorkspace({ drafts: retained }: { drafts?: Map<string, HumanDraft> }) {
  const own = useRef(new Map<string, HumanDraft>());
  const [filter, setFilter] = useState<HumanFilter>('decision');
  const inbox = useHuman(filter);
  const data = inbox.data;
  const items = data?.items.filter(item => matches(item, filter)) || [];
  return <section className="review-workspace human-workspace" aria-label="Solicitudes y decisiones">
    <header className="review-heading"><div><h2>Solicitudes y decisiones</h2><p>Decide qué seguir, qué dejar y qué acciones autorizar.</p></div><button className="secondary-button" onClick={inbox.refresh}>Actualizar solicitudes</button></header>
    <p className="review-help">Lecturas autorizadas y propuestas privadas pueden avanzar sin permiso por cada paso. Delegar no significa resolver.</p>
    <details className="human-runtime"><summary>Ejecutores y capacidades</summary>
      {data && <><div className="human-presence">{domains.map(domain => <article key={domain}><strong>{domain === 'support' ? 'Soporte' : 'MRs'}</strong><span>{data.controls[domain].available ? 'Ejecutor disponible' : 'Sin ejecutor confirmado'}</span><span>{data.controls[domain].paused ? 'Control pausado' : 'Control habilitado'} · {data.controls[domain].queued} en cola</span><p>No se arranca desde esta sección.</p></article>)}</div>
        <ul>{data.capabilities.map(capability => <li key={capability.kind}><strong>{capability.label}</strong><p>{capability.reason}</p></li>)}</ul></>}
    </details>
    {inbox.error && <p className="error-banner" role="alert">{inbox.error}<button className="text-button" onClick={inbox.refresh}>Actualizar estado</button></p>}
    <nav className="human-filters" aria-label="Filtrar solicitudes">{filters.map(value => <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{filterLabels[value]}</button>)}</nav>
    <div className="review-layout"><aside aria-label="Solicitudes recientes"><h3>{items.length} solicitudes · hasta {data?.limit_per_domain || 100} por tipo</h3>
      {items.map(item => <button className="review-choice" key={requestKey(item)} aria-pressed={inbox.selected === requestKey(item)} disabled={inbox.busy} onClick={() => inbox.setSelected(requestKey(item))}><span className="eyebrow">{item.domain === 'support' ? 'Soporte' : 'MR'}</span><strong>{item.title}</strong><span>{dispositionLabels[item.disposition]}</span><small>{item.conclusion ? 'Tiene conclusión guardada' : 'Sin conclusión'} · {item.actions.filter(action => !action.denied).length} acciones</small></button>)}
      {!items.length && <p className="review-help">No hay solicitudes en este filtro. Puedes revisar Todas, sin activar procesos.</p>}
    </aside>{inbox.detail && requestKey(inbox.detail.request) === inbox.selected ? <DecisionPanel key={inbox.selected} detail={inbox.detail} inbox={inbox} drafts={retained || own.current} /> : <section className="review-detail"><p className="review-help">Selecciona una solicitud para ver evidencia y decidir.</p></section>}</div>
  </section>;
}
