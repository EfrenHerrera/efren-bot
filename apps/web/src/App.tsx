import { useRef, useState } from 'react';
import '@/inbox.css';
import { ConversationWorkspace } from '@/ConversationWorkspace';
import { SupportWorkspace } from '@/SupportWorkspace';
import { ReviewWorkspace } from '@/ReviewWorkspace';
import type { ReviewDraft } from '@/use-review-draft';
import { HumanWorkspace } from '@/HumanWorkspace';
import { FactoryWorkspace } from '@/FactoryWorkspace';
import type { HumanDraft } from '@/human-client';
import { Drawer } from '@/Drawer';
import { useCollection } from '@/use-collection';
import { useInbox } from '@/use-inbox';
import { modeSchema, modes } from '@/collection-client';
import type { InboxMessage, RunStatus, Source } from '@/collection-client';

const labels: Record<RunStatus, string> = { queued: 'En espera', running: 'Recolectando', succeeded: 'Páginas disponibles recorridas', partial: 'Cobertura parcial', failed: 'No se completó' };
const dates = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' });
function date(value: string | null) { return value ? dates.format(new Date(value)) : 'Sin registro'; }
type Panel = 'activity' | 'sources' | 'variants' | null;

function SourceRow({ source, busy, save }: { source: Source; busy: boolean; save: (mode: Source['mode']) => void }) {
  const [mode, setMode] = useState(source.mode);
  return <li className="source-row"><div><strong>#{source.channel_name}</strong><p>{!source.available ? 'Acceso no confirmado en el último catálogo' : source.since ? `Completo desde ${date(source.since)}` : 'Canal de tu catálogo local'}</p></div>
    <div className="source-actions"><select aria-label={`Modo de ${source.channel_name}`} value={mode} onChange={event => { const next = modeSchema.safeParse(event.target.value); if (next.success) setMode(next.data); }}>
      {modeSchema.options.map(value => <option key={value} value={value} disabled={!source.available && value !== 'off'}>{modes[value]}</option>)}
    </select><button className="secondary-button" disabled={busy || mode === source.mode} onClick={() => save(mode)}>Guardar</button></div></li>;
}

export function App() {
  const reviewDrafts = useRef(new Map<string, ReviewDraft>());
  const humanDrafts = useRef(new Map<string, HumanDraft>());
  const collection = useCollection();
  const auxiliary = useInbox(0, false);
  const [panel, setPanel] = useState<Panel>(null);
  const [selected, setSelected] = useState<InboxMessage | null>(null);
  const [sourceSearch, setSourceSearch] = useState('');
  const [workspace, setWorkspace] = useState<'conversations' | 'support' | 'reviews' | 'human' | 'factory'>('conversations');
  const data = collection.data;
  const active = data?.active_run;
  const busy = collection.pending || auxiliary.busy;
  function variants(message: InboxMessage) { setSelected(message); setPanel('variants'); void auxiliary.loadVariants(message.id); }
  return <main className="workspace inbox-workspace">
    <header className="masthead"><a className="wordmark" href="/">efren<span>bot</span><span className="local-mark">local</span></a><span className="privacy-note">Tu revisión es local. No cambia Slack.</span></header>
    <section className="inbox-intro"><div><p className="eyebrow">Slack · Contexto y seguimiento</p><h1>Conversaciones</h1><p>Lee el contexto. Organiza solo los asuntos que te interesan.</p></div><div className="utility-actions"><button className="secondary-button" disabled={busy} onClick={() => { setPanel('sources'); void auxiliary.loadSources(); }}>Configurar fuentes</button><button className="secondary-button" onClick={() => setPanel('activity')}>Actividad de recolección{data?.runs[0]?.status === 'partial' ? ' · Parcial' : ''}</button></div></section>
    <section className="collection-strip" aria-label="Controles de recolección"><div><span className={`status-dot ${data?.runner_available ? 'available' : ''}`} /><strong>{!data ? 'Conectando…' : !data.activated_at ? 'Sin activar' : data.paused ? 'Automático pausado' : 'Automático cada 15 min'}</strong><span className="strip-detail">{active ? `${labels[active.status]} · ${active.page_count} páginas · ${active.added_count} registros añadidos` : data?.runner_available ? 'Ejecutor disponible' : 'Ejecutor desconectado'}</span></div>
      <div className="strip-buttons"><button className="text-button" disabled={!data || collection.pending} onClick={() => { if (data) void collection.command(!data.activated_at ? 'activate' : data.paused ? 'resume' : 'pause'); }}>{!data?.activated_at ? 'Activar automático' : data.paused ? 'Reanudar automático' : 'Pausar automático'}</button><button className="primary-button" disabled={!data?.runner_available || collection.pending || Boolean(active) || collection.error} onClick={() => { void collection.command('run'); }}>{active ? 'Recolección en curso' : 'Recolectar ahora'}</button></div>
    </section>
    {(collection.error || auxiliary.error) && <div className="error-banner" role="alert">{auxiliary.error || 'No se pudo actualizar la recolección. Comprueba la API y el ejecutor local.'}<button className="text-button" onClick={() => { void collection.refresh(); }}>Volver a intentar</button></div>}
    <nav className="workspace-tabs" aria-label="Área de trabajo"><button aria-pressed={workspace === 'conversations'} onClick={() => setWorkspace('conversations')}>Conversaciones</button><button aria-pressed={workspace === 'support'} onClick={() => setWorkspace('support')}>Investigaciones de soporte</button><button aria-pressed={workspace === 'reviews'} onClick={() => setWorkspace('reviews')}>Revisiones por decidir</button><button aria-pressed={workspace === 'human'} onClick={() => setWorkspace('human')}>Solicitudes y decisiones</button><button aria-pressed={workspace === 'factory'} onClick={() => setWorkspace('factory')}>Fábrica</button></nav>
    {workspace === 'factory' ? <FactoryWorkspace /> : workspace === 'human' ? <HumanWorkspace drafts={humanDrafts.current} /> : workspace === 'reviews' ? <ReviewWorkspace drafts={reviewDrafts.current} /> : workspace === 'support' ? <SupportWorkspace openConversation={() => setWorkspace('conversations')} /> : <ConversationWorkspace messageCount={data?.message_count || 0} variants={variants} />}
    {panel && <Drawer title={panel === 'activity' ? 'Actividad de recolección' : panel === 'sources' ? 'Configurar fuentes' : 'Representaciones conservadas'} close={() => setPanel(null)}>
      {auxiliary.error && <p className="error-banner" role="alert">{auxiliary.error}</p>}
      {panel === 'activity' && <><p className="drawer-note">Próxima automática: {date(data?.next_due_at || null)}. Necesita el host despierto y su ejecutor activo.</p><p className="drawer-note">La búsqueda depende del índice y los permisos de Slack; agotar páginas no prueba una exportación completa.</p><ol className="run-list">{data?.runs.map(run => <li key={run.id}><span className={`pill ${run.status}`}>{run.trigger === 'import' && run.status === 'succeeded' ? 'Historial importado' : labels[run.status]}</span><span className="run-trigger">{run.trigger === 'manual' ? 'Manual' : run.trigger === 'import' ? 'Archivo local' : 'Automática'}</span><p>{date(run.created_at)} · {run.page_count} capturas · {run.added_count} registros añadidos</p>{run.error_code && <p className="run-error">{run.error_code}. Las fuentes confirmadas conservan su avance.</p>}{run.coverage.some(item => item.state === 'partial') && <details><summary>Ver fuentes pendientes</summary><ul>{run.coverage.filter(item => item.state === 'partial').map((item, index) => <li key={`${item.scope}-${index}`}>{item.scope}: {item.code}</li>)}</ul></details>}</li>)}</ol>{data?.runs.length === 0 && <p className="empty-small">Todavía no hay ejecuciones.</p>}</>}
      {panel === 'sources' && <><p className="drawer-note">Canales de tu catálogo de membresía guardado. Añadir captura completa empieza desde que guardas; no importa historia. Desactivar no borra mensajes. Los cambios se aplican a siguientes ejecuciones.</p><p className="drawer-note">Los DMs propios siguen incluidos. El histórico importado no habilita canales automáticamente.</p><label className="drawer-search">Buscar canal<input type="search" value={sourceSearch} onChange={event => setSourceSearch(event.target.value)} /></label><p className="small-label">Catálogo observado: {date(auxiliary.sources?.observed_at || null)}</p>{!auxiliary.sources ? <p role="status">Consultando fuentes…</p> : <ul className="source-list">{auxiliary.sources.channels.filter(source => source.channel_name.toLocaleLowerCase().includes(sourceSearch.toLocaleLowerCase())).map(source => <SourceRow key={source.channel_id} source={source} busy={busy} save={mode => { void auxiliary.saveSource(source, mode); }} />)}</ul>}</>}
      {panel === 'variants' && <><p className="drawer-note">Representaciones del conector, no una historia verificada de ediciones. Se conservan sin fusionar el contenido.</p>{!auxiliary.variants ? <p role="status">Cargando representaciones…</p> : <>{auxiliary.variants.messages.map(message => <article className="variant-message" key={message.id}><time>{date(message.observed_at)}</time><span className="pill muted">{message.is_historical ? 'Archivo histórico' : 'Recolección'}</span><p className="message-text">{message.text || 'Sin texto disponible.'}</p></article>)}{selected && auxiliary.variants.next_offset !== null && <button className="secondary-button full" disabled={auxiliary.busy} onClick={() => { if (selected && auxiliary.variants?.next_offset !== null && auxiliary.variants?.next_offset !== undefined) void auxiliary.loadVariants(selected.id, auxiliary.variants.next_offset); }}>Cargar más representaciones</button>}</>}</>}
    </Drawer>}
  </main>;
}
