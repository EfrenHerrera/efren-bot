import { useId, useRef, useState } from 'react';
import { dimensionLabels, phaseLabels, reviewLabels } from '@/review-client';
import type { Proposal, ReviewDetail } from '@/review-client';
import { CodeBlock, ReviewText } from '@/ReviewText';
import { useReviews } from '@/use-reviews';
import { useReviewDraft } from '@/use-review-draft';
import type { ReviewDraft } from '@/use-review-draft';
import '@/review.css';

const dates = new Intl.DateTimeFormat('es-MX', { dateStyle: 'short', timeStyle: 'short' });
const checkLabels = { reviewed: 'Con evidencia estática', limited: 'Por corroborar', not_applicable: 'No aplica al cambio' };
const tabs = ['Resumen', 'Análisis', 'Conversación'];
type Reviews = ReturnType<typeof useReviews>;

function Evidence({ references, detail }: { references: Array<{ source_id: string; quote: string }>; detail: ReviewDetail }) {
  if (!references.length) return <p className="review-help">Sin referencias adicionales.</p>;
  return <details className="review-citations"><summary>Ver evidencia · {references.length}</summary>
    {references.map((reference, index) => {
      const source = detail.item.snapshot.sources?.find(source => source.id === reference.source_id);
      const isCode = source?.kind === 'diff' || source?.kind === 'file' || source?.kind === 'ci';
      const extension = source?.path?.split('.').at(-1) || 'text';
      return <article key={`${reference.source_id}-${index}`}>
        <div className="review-source-meta"><span>{reference.source_id} · Fragmento citado</span>{source?.sha && <code title={source.sha}>{source.sha.slice(0, 12)}</code>}</div>
        {isCode ? <CodeBlock text={reference.quote} label={source?.path || 'CI capturada'} language={source?.kind === 'diff' ? 'diff' : source?.kind === 'ci' ? 'json' : extension} />
          : <blockquote><span className="review-help">{source?.path || (source?.kind === 'discussion' ? 'Discusión en GitLab' : 'Fuente guardada')}</span><ReviewText text={reference.quote} /></blockquote>}
      </article>;
    })}
  </details>;
}

function Conclusion({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const canExpand = text.length > 420;
  return <div className="review-conclusion">
    <div className="review-summary-text" data-collapsed={canExpand && !expanded}><ReviewText text={text} /></div>
    {canExpand && <button className="text-button" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? 'Mostrar menos' : 'Leer conclusión completa'}</button>}
  </div>;
}

function ReviewPanel({ reviews, detail, drafts }: { reviews: Reviews; detail: ReviewDetail; drafts: Map<string, ReviewDraft> }) {
  const { text, setText, redirect, setRedirect, requestKey, setRequestKey, editing, setEditing, body, setBody, editKey, setEditKey } = useReviewDraft(detail.item.id, drafts);
  const [copied, setCopied] = useState<string | null>(null);
  const [copyError, setCopyError] = useState(false);
  const [tab, setTab] = useState('Resumen');
  const panelId = useId();
  const { item, request } = detail;
  const currentReport = item.report.revision === item.revision ? item.report : null;
  const latest = detail.proposals.filter(proposal => proposal.revision === item.revision);
  const proposalCount = latest.filter(proposal => proposal.status !== 'discarded').length;
  const busy = reviews.busy;
  const inProgress = item.status === 'running' || item.status === 'queued';
  const pending = currentReport?.pending || [];
  const limitations = item.snapshot.limitations || [];
  async function send() {
    if (await reviews.act(redirect ? 'redirect' : 'ask', text, requestKey)) { setText(''); setRequestKey(crypto.randomUUID()); }
  }
  async function save() {
    if (editing && await reviews.act('edit', body, editKey, editing)) { setEditing(null); setBody(''); }
  }
  function publish(proposal: Proposal) {
    if (window.confirm(`Publicar SOLO este comentario en !${item.mr_iid}, head ${item.snapshot.refs?.head_sha.slice(0, 12)}?\n\n${proposal.body}\n\nNo aprueba la MR ni resuelve hilos.`)) void reviews.act('publish', '', crypto.randomUUID(), proposal);
  }
  async function copy(proposal: Proposal) {
    try { await navigator.clipboard.writeText(proposal.body); setCopied(proposal.id); setCopyError(false); }
    catch { setCopyError(true); }
  }
  return <section className="review-detail" aria-label="Detalle de revisión">
    <header className="review-detail-heading">
      <div><a className="review-mr-link" href={item.url} target="_blank" rel="noopener noreferrer">{item.project_path.split('/').at(-1)} / !{item.mr_iid} ↗</a><h3>{item.title}</h3></div>
      <div className="review-controls"><button className="secondary-button" disabled={busy} onClick={() => { void reviews.act(item.status === 'paused' || item.status === 'failed' ? 'resume' : 'pause', '', crypto.randomUUID()); }}>{item.status === 'paused' || item.status === 'failed' ? 'Reanudar / volver a capturar' : 'Pausar MR'}</button><button className="text-button" onClick={reviews.refresh}>Actualizar</button></div>
    </header>
    <div className="review-status-row"><span className="review-state" data-status={item.status}>{reviewLabels[item.status]}</span><span>{request.demo ? 'Demo · no publica' : 'Propuestas privadas'} · Revisión {item.revision}</span>{item.snapshot.refs && <code title={item.snapshot.refs.head_sha}>{item.snapshot.refs.head_sha.slice(0, 12)}</code>}</div>
    {inProgress && <p className="review-progress" role="status">{phaseLabels[item.phase]}</p>}
    {item.error_code && <p className="error-banner" role="status">{item.error_code === 'mr_changed_during_review' ? 'El código cambió durante la revisión. Vuelve a capturar para decidir sobre esta versión.' : `No se completó esta etapa: ${item.error_code}`}</p>}
    {item.snapshot.mr_state && item.snapshot.mr_state !== 'opened' && <p className="review-compact-notice">MR {item.snapshot.mr_state === 'merged' ? 'mergeada' : item.snapshot.mr_state} · Solo contexto; publicación deshabilitada.</p>}
    {item.report.revision !== undefined && !currentReport && <p className="review-compact-notice">El informe anterior ya no es vigente. Sus propuestas no se pueden publicar.</p>}
    {editing && !latest.some(proposal => proposal.id === editing.id) && <section className="review-stale-draft"><h4>Borrador anterior conservado</h4><p>La versión cambió. Tu texto no se aplicará a otra revisión.</p><textarea aria-label="Borrador anterior conservado" value={body} onChange={event => setBody(event.target.value)} /><button className="secondary-button" onClick={() => { setEditing(null); setBody(''); }}>Descartar este borrador local</button></section>}
    <nav className="review-panel-nav" aria-label="Contenido de la revisión">{tabs.map(name => <button key={name} aria-pressed={tab === name} aria-controls={`${panelId}-${name}`} onClick={() => setTab(name)}>{name}{name === 'Análisis' && <span>{currentReport?.checks?.length || 0}</span>}</button>)}</nav>

    <section id={`${panelId}-Resumen`} hidden={tab !== 'Resumen'} className="review-panel-content">
      <div className="review-section-heading"><h4>Conclusión</h4><span className="review-help">Inspección estática, no aprobación</span></div>
      {currentReport?.summary ? <Conclusion text={currentReport.summary} /> : <p className="review-help">{inProgress ? 'La revisión está en curso. Aquí aparecerá su conclusión.' : 'No hay una conclusión vigente para esta revisión.'}</p>}
      {(item.status === 'partial' || Boolean(pending.length || limitations.length)) && <section className="review-gaps" aria-label="Cobertura incompleta">
        <strong>Falta evidencia para cerrar la revisión</strong><p>Consulta los faltantes antes de tomar una decisión.</p>
        {Boolean(pending.length) && <details><summary>Comprobaciones pendientes <span>{pending.length}</span></summary><ul>{pending.map(value => <li key={value}><ReviewText text={value} /></li>)}</ul><p className="review-help">Esta lista no ejecuta comandos. Tocar otro entorno requiere autorización.</p></details>}
        {Boolean(limitations.length) && <details><summary>Límites de lectura <span>{limitations.length}</span></summary><ul className="review-reading-limits">{limitations.map(value => <li key={value}>{value}</li>)}</ul></details>}
      </section>}
      <section className="review-proposals" aria-label="Propuestas privadas">
        <div className="review-section-heading"><h4>Comentarios para decidir</h4><span className="review-count">{proposalCount}</span></div>
        {latest.length === 0 && <div className="review-empty"><strong>{inProgress ? 'Todavía no hay propuestas' : 'Sin comentarios propuestos'}</strong><p>{inProgress ? 'Aparecerán aquí si el análisis encuentra observaciones sustentadas.' : 'No hay observaciones nuevas con evidencia suficiente. Esto no garantiza ausencia de defectos.'}</p></div>}
        {latest.map(proposal => <article className="review-proposal" key={proposal.id} data-status={proposal.status}>
          <header><span className="review-severity" data-severity={proposal.finding.severity}>{proposal.finding.severity === 'high' ? 'Alta' : proposal.finding.severity === 'medium' ? 'Media' : 'Baja'}</span><span>{proposal.status === 'private' ? 'Privado' : proposal.status === 'published' ? 'Publicado' : proposal.status === 'uncertain' ? 'Envío incierto · no reintentar' : proposal.status === 'discarded' ? 'Descartado' : proposal.status}</span></header>
          <h5>{proposal.finding.problem}</h5><code className="review-file-path">{proposal.finding.path}:{proposal.finding.line}</code>
          <div className="review-comment"><ReviewText text={proposal.body} /></div>
          <details className="review-rationale"><summary>Por qué se propone este comentario</summary><dl><dt>Escenario</dt><dd><ReviewText text={proposal.finding.scenario} /></dd><dt>Impacto</dt><dd><ReviewText text={proposal.finding.impact} /></dd><dt>Alternativa</dt><dd><ReviewText text={proposal.finding.alternative} /></dd></dl><Evidence references={proposal.finding.evidence} detail={detail} /></details>
          {editing?.id === proposal.id ? <form onSubmit={event => { event.preventDefault(); void save(); }}>
            <label>Editar comentario privado<textarea value={body} maxLength={5000} disabled={busy} onChange={event => { setBody(event.target.value); setEditKey(crypto.randomUUID()); }} /></label>
            <div className="review-controls"><button type="button" className="secondary-button" disabled={busy} onClick={() => setEditing(null)}>Cancelar edición</button><button className="primary-button" disabled={busy || !body.trim()}>Guardar comentario privado</button></div>
          </form> : <div className="review-controls review-proposal-actions">
            <button className="secondary-button" disabled={busy || proposal.status !== 'private' || Boolean(editing)} onClick={() => { setEditing(proposal); setBody(proposal.body); setEditKey(crypto.randomUUID()); }}>Editar propuesta</button>
            <button className="text-button" disabled={busy || proposal.status !== 'private'} onClick={() => { void reviews.act('discard', '', crypto.randomUUID(), proposal); }}>Descartar propuesta</button>
            <button className="secondary-button" disabled={request.demo || !reviews.data?.publication_enabled || item.status !== 'ready' || proposal.status !== 'private' || item.snapshot.mr_state !== 'opened' || busy || Boolean(editing)} title={request.demo ? 'La demo nunca publica' : 'Requiere confirmación y versión vigente'} onClick={() => publish(proposal)}>Publicar este comentario</button>
            <button className="text-button" onClick={() => { void copy(proposal); }}>{copied === proposal.id ? 'Copiado' : 'Copiar borrador'}</button>
          </div>}
        </article>)}
        {copyError && <p role="status">No se pudo copiar el borrador. Puedes seleccionarlo o abrir su edición.</p>}
      </section>
    </section>

    <section id={`${panelId}-Análisis`} hidden={tab !== 'Análisis'} className="review-panel-content">
      <div className="review-section-heading"><h4>Cobertura técnica</h4><span className="review-help">Abre una dimensión para ver su evidencia</span></div>
      <div className="review-checks">{currentReport?.checks?.map(check => <details key={check.dimension} data-status={check.status}>
        <summary><strong>{dimensionLabels[check.dimension]}</strong><span>{checkLabels[check.status]}</span></summary>
        <ReviewText text={check.conclusion} /><Evidence references={check.evidence} detail={detail} />
      </details>)}</div>
      {!currentReport && <p className="review-help">Aún no hay un análisis vigente. Puedes preguntar por el avance en Conversación.</p>}
      {Boolean(currentReport?.previous?.length) && <details className="review-history"><summary>Comentarios anteriores <span>{currentReport?.previous?.length}</span></summary>
        <p className="review-help">Se contrastan con el código; no se duplican ni se cierran automáticamente.</p>
        {currentReport?.previous?.map(previous => <details key={previous.discussion_id} className="review-previous"><summary>{previous.status === 'addressed_in_code' ? 'Corrección contrastada con código' : previous.status === 'accepted_followup' ? 'Seguimiento ya acordado' : previous.status === 'needs_validation' ? 'Falta revalidar' : 'Observación todavía relevante'}</summary><ReviewText text={previous.assessment} /><Evidence references={previous.evidence} detail={detail} /></details>)}
      </details>}
      <details className="review-plan"><summary>Versión y plan de revisión</summary>
        <dl><dt>Head capturado</dt><dd><code>{item.snapshot.refs?.head_sha || 'Sin capturar'}</code></dd><dt>Etapa</dt><dd>{phaseLabels[item.phase]}</dd></dl>
        {item.plan.objective && <><ReviewText text={item.plan.objective} /><ul>{item.plan.hypotheses?.map(hypothesis => <li key={hypothesis}><ReviewText text={hypothesis} /></li>)}</ul><details><summary>Rangos solicitados · {item.plan.reads?.length || 0}</summary><ol>{item.plan.reads?.map((read, index) => <li key={`${read.path}-${index}`}><code>{read.path}:{read.start}–{read.end}</code> · {read.side}<ReviewText text={read.reason} /></li>)}</ol></details></>}
      </details>
    </section>

    <section id={`${panelId}-Conversación`} hidden={tab !== 'Conversación'} className="review-panel-content review-chat">
      <h4>Dirige esta revisión</h4><p className="review-help">Preguntar no reinicia el análisis. Cambiar el enfoque sí programa una nueva revisión.</p>
      <ol>{detail.entries.filter(entry => entry.kind === 'ask' || entry.kind === 'answer' || entry.kind === 'redirect').map(entry => <li key={entry.id} data-kind={entry.kind}>
        <strong>{entry.kind === 'ask' ? 'Tu pregunta' : entry.kind === 'answer' ? 'Respuesta con evidencia disponible' : 'Cambio de rumbo'}</strong>
        <ReviewText text={entry.text} /><small>{entry.status === 'queued' || entry.status === 'running' ? 'Pendiente' : entry.status === 'failed' ? 'No se completó' : dates.format(new Date(entry.created_at))}</small>
      </li>)}</ol>
      <form onSubmit={event => { event.preventDefault(); void send(); }}>
        <label>Mensaje para esta revisión<textarea required maxLength={4000} value={text} disabled={busy} onChange={event => { setText(event.target.value); setRequestKey(crypto.randomUUID()); }} /></label>
        <label className="review-redirect"><input type="checkbox" checked={redirect} disabled={busy} onChange={event => { setRedirect(event.target.checked); setRequestKey(crypto.randomUUID()); }} />Cambiar el enfoque y volver a revisar (no ejecutar código)</label>
        <button className="primary-button" disabled={busy || !text.trim()}>{redirect ? 'Guardar cambio de rumbo' : 'Preguntar sobre el avance'}</button>
      </form>
      <details className="review-history"><summary>Historial de resultados y decisiones</summary><ol>{detail.entries.filter(entry => !['archive', 'ask', 'answer', 'redirect'].includes(entry.kind)).map(entry => <li key={entry.id}>
        <strong>{entry.kind === 'report' ? 'Resultado guardado' : entry.kind === 'stage_failed' ? 'Etapa no completada' : entry.kind === 'publish' ? 'Autorización de publicación' : 'Decisión humana'}</strong><ReviewText text={entry.text} /><small>{entry.status === 'uncertain' ? 'Resultado remoto incierto · no se reintenta automáticamente' : entry.status}</small>
      </li>)}</ol></details>
    </section>
  </section>;
}

export function ReviewWorkspace({ drafts: retainedDrafts, targetId }: { drafts?: Map<string, ReviewDraft>; targetId?: string }) {
  const ownDrafts = useRef(new Map<string, ReviewDraft>());
  const drafts = retainedDrafts || ownDrafts.current;
  const reviews = useReviews(targetId);
  const control = reviews.data?.control;
  const [demoKey] = useState(() => crypto.randomUUID());
  if (targetId) return <section className="review-workspace" aria-label="Revisión de la solicitud">
    {reviews.error && <p className="error-banner" role="alert">{reviews.error}<button className="text-button" onClick={reviews.refresh}>Actualizar estado</button></p>}
    {reviews.detail?.item.id === targetId ? <ReviewPanel key={targetId} detail={reviews.detail} reviews={reviews} drafts={drafts} /> : <p role="status">Cargando la revisión seleccionada…</p>}
    <details className="request-settings"><summary>Configuración avanzada de revisiones</summary><p className="review-help">Control global, independiente de esta solicitud. No arranca el proceso host.</p><button className="secondary-button" disabled={!control || reviews.busy} onClick={() => { void reviews.command(!control?.activated_at ? 'activate' : control.paused ? 'resume' : 'pause', {}); }}>{!control?.activated_at ? 'Activar solo lo nuevo' : control.paused ? 'Reanudar revisiones' : 'Pausar revisiones'}</button><p className="review-help">{control?.runner_available ? 'Ejecutor disponible' : 'Ejecutor no confirmado'} · Solo Core y konfio-app-web. Sin ejecución de código, aprobación ni merge.</p></details>
  </section>;
  return <section className="review-workspace" aria-label="Revisiones por decidir">
    <header className="review-heading"><div><h2>Revisiones por decidir</h2><p>Una conclusión clara. La evidencia, cuando la necesites.</p></div>
      <button className="secondary-button" disabled={!control || reviews.busy} onClick={() => { void reviews.command(!control?.activated_at ? 'activate' : control.paused ? 'resume' : 'pause', {}); }}>{!control?.activated_at ? 'Activar solo lo nuevo' : control.paused ? 'Reanudar revisiones' : 'Pausar revisiones'}</button>
    </header>
    <div className="review-runtime"><span className="review-runtime-dot" data-available={control?.runner_available} />{control?.runner_available ? 'Ejecutor disponible' : 'Ejecutor no confirmado'}<span>· {!control?.activated_at ? 'Sin activar' : control.paused ? 'Automático pausado' : 'Solo solicitudes nuevas'}</span>
      <details><summary>Alcance y permisos</summary><div><p>Solo Core y konfio-app-web. Sin barrido histórico, checkout, ejecución de código, aprobación o merge.</p><p>La inspección es estática, no certifica funcionamiento. Publicar requiere confirmar un comentario y su versión exactos. La demo nunca publica.</p><p>{control?.activated_at ? `Solicitudes nuevas desde ${dates.format(new Date(control.activated_at))}.` : 'Todavía no hay un corte de activación.'}</p></div></details>
    </div>
    {reviews.error && <p className="error-banner" role="alert">{reviews.error}<button className="text-button" onClick={reviews.refresh}>Actualizar estado</button></p>}
    {!reviews.data?.items.some(item => item.demo) && <button className="secondary-button" disabled={reviews.busy || !reviews.data} onClick={() => { void reviews.command('demo', { request_id: demoKey }); }}>Probar el hilo autorizado: 3 MRs, sin publicar</button>}
    <div className="review-layout"><aside aria-label="Todas las MRs solicitadas"><h3>{reviews.data?.items.length || 0} MRs recientes</h3>
      {reviews.data?.items.map(item => <button className="review-choice" key={item.id} aria-label={`!${item.mr_iid} · ${item.title}. ${reviewLabels[item.status]}`} aria-pressed={reviews.selected === item.id} disabled={reviews.busy} onClick={() => reviews.setSelected(item.id)}>
        <span className="review-choice-id">!{item.mr_iid}<small>{item.project_path.split('/').at(-1)}{item.demo ? ' · demo' : ''}</small></span><strong>{item.title}</strong>
        <span className="review-state" data-status={item.status}>{reviewLabels[item.status]}</span>
        <small>{item.status === 'running' || item.status === 'queued' ? phaseLabels[item.phase] : `${item.source_count} fuentes · ${item.proposal_count} propuestas`}</small>
      </button>)}
      {reviews.data?.items.length === 0 && <p className="review-help">No hay solicitudes nuevas. No se revisó el histórico por extensión.</p>}
    </aside>{reviews.detail && reviews.detail.item.id === reviews.selected ? <ReviewPanel key={reviews.detail.item.id} detail={reviews.detail} reviews={reviews} drafts={drafts} /> : <section className="review-detail"><p className="review-help">Selecciona una MR para seguir el análisis y decidir sobre sus propuestas.</p></section>}</div>
    <details className="review-requests"><summary>Actividad de solicitudes</summary><ul>{reviews.data?.requests.map(request => <li key={request.id}>{request.demo ? 'Demo aislada' : 'Mensaje nuevo'} · {request.status}{request.decision.reason ? ` · ${request.decision.reason}` : ''}{request.error_code ? ` · ${request.error_code}` : ''}</li>)}</ul></details>
  </section>;
}
