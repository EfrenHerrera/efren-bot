import { useEffect, useState } from 'react';
import { attentionSchema, attentions, categories, categorySchema } from '@/collection-client';
import { conversationKey, conversationView } from '@/conversation-client';
import type { ContextMessage, Group, GroupDraft } from '@/conversation-client';
import { useConversations } from '@/use-conversations';
import '@/conversations.css';

const dates = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' });
const viewLabels = { all: 'Todas', mentions: 'Te mencionan', following: 'En seguimiento', new: 'Actividad nueva' };
function date(value: string) { return dates.format(new Date(value)); }

function MentionText({ text, self }: { text: string; self: string }) {
  const tokens = text.split(/(<@[UW][A-Z0-9]+(?:\|[^>\n]*)?>)/g);
  return <>{tokens.map((token, index) => {
    const mention = /^<@([UW][A-Z0-9]+)(?:\|([^>\n]*))?>$/.exec(token);
    if (!mention) return token;
    return mention[1] === self ? <mark key={index} title="Mención literal a tu usuario">Tú</mark> : <span key={index} title={mention[1]}>@{mention[2] || mention[1]}</span>;
  })}</>;
}

function ContextEntry({ message, self, root, draft, toggle, variants }: { message: ContextMessage; self: string; root: boolean; draft: GroupDraft | null; toggle: (id: string) => void; variants: (message: ContextMessage) => void }) {
  return <article id={`context-${message.id}`} tabIndex={-1} className={`context-entry ${message.mentions_me ? 'context-mention' : ''} ${root ? 'context-root' : ''}`}>
    <header><div><strong>{root ? 'Inicio guardado' : 'Mensaje del contexto'}</strong><span className="author-label">{message.actor_id || 'Autor no disponible'}</span></div><time dateTime={message.occurred_at}>{date(message.occurred_at)}</time></header>
    {message.mentions_me && <span className="mention-label">Hay una mención a tu usuario</span>}
    <p className="message-text"><MentionText text={message.text || 'Sin texto disponible; puede incluir un adjunto no descargado.'} self={self} /></p>
    {message.mentions_me && message.mention_excerpt && message.mention_excerpt !== message.text && <div className="alternate-mention"><small>Mención en otra representación conservada</small><p className="message-text"><MentionText text={message.mention_excerpt} self={self} /></p></div>}
    {draft && <label className="evidence-checkbox"><input type="checkbox" checked={draft.message_ids.includes(message.id)} onChange={() => toggle(message.id)} />Vincular este mensaje al asunto</label>}
    <details className="context-source"><summary>Fuente y representaciones</summary><div>{message.variant_count > 1 && <button className="text-button" onClick={() => variants(message)}>{message.variant_count} representaciones</button>}{message.source_url && <a href={message.source_url} target="_blank" rel="noopener noreferrer">Abrir fuente en Slack ↗</a>}<span>{message.historical ? 'Archivo histórico' : 'Recolección reciente'}</span></div></details>
  </article>;
}

export function ConversationWorkspace({ messageCount, variants }: { messageCount: number; variants: (message: ContextMessage) => void }) {
  const [draft, setDraft] = useState<GroupDraft | null>(null);
  const conversations = useConversations(messageCount, draft !== null);
  const [mobileContext, setMobileContext] = useState(false);
  const [focus, setFocus] = useState({ id: '', serial: 0 });
  const selectedKey = conversations.selected ? conversationKey(conversations.selected) : null;
  const detail = conversations.detail;
  const selected = conversations.selected;
  const busy = conversations.saving;
  useEffect(() => { setDraft(null); setFocus({ id: '', serial: 0 }); }, [selectedKey]);
  useEffect(() => {
    const element = document.querySelector(mobileContext ? '.conversation-detail' : '.conversation-choice[aria-pressed="true"]');
    if (element instanceof HTMLElement && element.getClientRects().length && typeof element.scrollIntoView === 'function') element.scrollIntoView({ block: mobileContext ? 'start' : 'nearest' });
  }, [selectedKey, mobileContext]);
  useEffect(() => {
    if (!focus.id || !detail?.messages.some(message => message.id === focus.id)) return;
    const element = document.getElementById(`context-${focus.id}`);
    if (element && typeof element.scrollIntoView === 'function') { element.scrollIntoView({ block: 'center', behavior: 'auto' }); element.focus({ preventScroll: true }); }
  }, [focus, detail]);

  function begin(group?: Group) {
    setDraft(group ? { id: group.id, revision: group.revision, request_id: crypto.randomUUID(), title: group.title, category: group.category, attention: group.attention, message_ids: group.message_ids } : { request_id: crypto.randomUUID(), title: '', category: 'unclassified', attention: 'undecided', message_ids: [] });
  }
  function toggle(id: string) { setDraft(previous => previous ? { ...previous, message_ids: previous.message_ids.includes(id) ? previous.message_ids.filter(value => value !== id) : [...previous.message_ids, id] } : null); }
  async function save() { if (draft && await conversations.saveGroup(draft)) setDraft(null); }
  function jump(id: string, offset: number) { conversations.setContextOffset(offset); setFocus(previous => ({ id, serial: previous.serial + 1 })); }

  return <section className="conversation-workspace" aria-label="Bandeja de conversaciones">
    {conversations.error && <div className="error-banner" role="alert">{conversations.error}<button className="text-button" onClick={conversations.refresh}>Actualizar contexto</button></div>}
    <fieldset className="conversation-tools" disabled={draft !== null || busy}>
      <div className="review-tabs" role="group" aria-label="Vistas de conversaciones">{conversationView.options.map(value => <button key={value} aria-pressed={conversations.filters.view === value} onClick={() => { setMobileContext(false); conversations.changeFilters({ ...conversations.filters, view: value }); }}>{viewLabels[value]}</button>)}</div>
      <div className="conversation-search"><input aria-label="Buscar en todo el contexto" type="search" placeholder="Buscar en conversaciones y respuestas…" value={conversations.filters.query} onChange={event => conversations.changeFilters({ ...conversations.filters, query: event.target.value })} /><details><summary>Filtrar por canal o asunto</summary><div className="conversation-filter-fields">
        <label>Canal<select aria-label="Canal de conversación" value={conversations.filters.channel_id} onChange={event => conversations.changeFilters({ ...conversations.filters, channel_id: event.target.value })}><option value="">Todos los canales</option>{conversations.data?.channels.map(channel => <option key={`${channel.channel_id}-${channel.channel_name}`} value={channel.channel_id}>{channel.channel_name}</option>)}</select></label>
        <label>Tipo de asunto<select value={conversations.filters.category} onChange={event => { const value = categorySchema.safeParse(event.target.value); if (value.success || event.target.value === '') conversations.changeFilters({ ...conversations.filters, category: value.success ? value.data : '' }); }}><option value="">Cualquier tipo</option>{categorySchema.options.map(value => <option value={value} key={value}>{categories[value]}</option>)}</select></label>
        <label>Atención del asunto<select value={conversations.filters.attention} onChange={event => { const value = attentionSchema.safeParse(event.target.value); if (value.success || event.target.value === '') conversations.changeFilters({ ...conversations.filters, attention: value.success ? value.data : '' }); }}><option value="">Cualquier atención</option>{attentionSchema.options.map(value => <option value={value} key={value}>{attentions[value]}</option>)}</select></label>
      </div></details><button className="text-button" onClick={conversations.refresh}>Actualizar bandeja</button></div>
    </fieldset>
    <div className={`conversation-layout ${mobileContext ? 'show-mobile-context' : ''}`}>
      <aside className="conversation-list-column" aria-label="Lista de conversaciones"><div className="conversation-list-heading" aria-live="polite"><strong>{conversations.data ? `${conversations.data.total} conversaciones` : 'Cargando conversaciones…'}</strong><span>{conversations.loading ? 'Actualizando…' : 'Por última actividad'}</span></div>
        <div className="conversation-list">{conversations.data?.conversations.map(item => <button className="conversation-choice" key={conversationKey(item)} aria-pressed={selectedKey === conversationKey(item)} disabled={draft !== null || busy} onClick={() => { conversations.choose(item); setMobileContext(true); }}><span className="conversation-channel">#{item.channel_name}</span><span className="conversation-preview">{item.root_present ? <MentionText text={item.preview || 'Inicio sin texto disponible'} self={detail?.self_user_id || ''} /> : 'Inicio del hilo no guardado'}</span><span className="conversation-counts">{item.message_count} mensajes{item.mention_count > 0 ? ` · ${item.mention_count} con mención a ti` : ''}</span><span className="conversation-signals">{item.group_count > 0 && <span>{item.group_count} asuntos</span>}{item.new_count > 0 && <span>{item.new_count} mensajes nuevos</span>}{item.relation_status !== 'confirmed' && <span>{item.relation_status === 'conflict' ? 'Relación en conflicto' : 'Sin hilo confirmado'}</span>}</span><time>{date(item.last_activity_at)}</time></button>)}</div>
        {conversations.data?.conversations.length === 0 && <div className="empty-small">{conversations.filters.view === 'following' ? 'Solo aparecerán aquí las conversaciones en las que decidas organizar un asunto.' : conversations.filters.view === 'new' ? 'No hay actividad nueva en esta vista. El archivo histórico no se cuenta como nuevo.' : 'No hay conversaciones con estos filtros.'}</div>}
        {conversations.data && conversations.data.total > 0 && <nav className="conversation-pages" aria-label="Páginas de conversaciones"><button disabled={draft !== null || busy || conversations.loading || conversations.offset === 0} onClick={() => conversations.setOffset(Math.max(0, conversations.offset - 50))}>Anterior</button><span>{conversations.offset + 1}–{conversations.offset + conversations.data.conversations.length}</span><button disabled={draft !== null || busy || conversations.loading || conversations.data.next_offset === null} onClick={() => { if (conversations.data?.next_offset !== null && conversations.data?.next_offset !== undefined) conversations.setOffset(conversations.data.next_offset); }}>Siguiente</button></nav>}
      </aside>
      <section className="conversation-detail" aria-label="Contexto de la conversación" aria-busy={conversations.contextLoading}>
        <button className="text-button back-to-conversations" disabled={draft !== null || busy} onClick={() => setMobileContext(false)}>← Volver a conversaciones</button>
        {!selected ? <div className="empty-feed"><h2>El contexto, no los comentarios sueltos</h2><p>Selecciona una conversación. No necesitas clasificar cada mensaje ni convertir todo en trabajo.</p></div> : !detail || conversations.contextLoading ? <p className="context-loading" role="status">Cargando el contexto guardado…</p> : <>
          <header className="conversation-detail-heading"><div><p className="eyebrow">Conversación en #{detail.conversation.channel_name}</p><h2>{detail.total} mensajes de contexto</h2></div><button className="text-button" disabled={busy || draft !== null} onClick={conversations.refresh}>Actualizar contexto</button></header>
          {detail.conversation.relation_status !== 'confirmed' && <p className="context-warning">{detail.conversation.relation_status === 'conflict' ? 'Hay referencias contradictorias. Este mensaje se conserva separado; no se han inventado relaciones.' : 'No hay relación de hilo confirmada para este mensaje. No se ha agrupado por parecido.'}</p>}
          {!detail.conversation.root_present && <p className="context-warning">El mensaje inicial no está guardado. Puedes leer el contexto disponible, pero no se presenta como completo.</p>}
          {detail.mention_locations.length > 0 && <section className="mention-strip" aria-label="Menciones en el contexto"><strong>Te mencionan en {detail.mention_locations.length} {detail.mention_locations.length === 1 ? 'mensaje' : 'mensajes'} del contexto</strong><p>Puede estar en cualquier respuesta, no solo al inicio. Una mención literal —incluso citada— no prueba un encargo.</p><div>{detail.mention_locations.map((mention, index) => <button key={mention.id} onClick={() => jump(mention.id, mention.offset)}>Ir a mención {index + 1}</button>)}</div></section>}
          <section className="conversation-followups" aria-label="Asuntos de la conversación"><div className="followup-heading"><div><h3>{detail.groups.length ? `${detail.groups.length} ${detail.groups.length === 1 ? 'asunto' : 'asuntos'} en seguimiento` : '¿Hay algo que quieras seguir?'}</h3><p>Puede ser un asunto, varios o ninguno. Tú decides después de leer.</p></div>{!draft && <button className="secondary-button" disabled={busy} onClick={() => begin()}>{detail.groups.length ? 'Añadir otro asunto' : 'Organizar un asunto'}</button>}</div>
            <ul className="followup-list">{detail.groups.map(group => <li key={group.id}><div><strong>{group.title}</strong><p>{categories[group.category]} · {attentions[group.attention]}</p><small>{group.all_context ? 'Vinculado a la conversación completa' : `${group.evidence_count} mensajes vinculados`}</small></div><div><button className="text-button" disabled={busy || draft !== null} onClick={() => begin(group)}>Editar asunto</button><button className="text-button" disabled={busy || draft !== null} onClick={() => { void conversations.removeGroup(group); }}>Quitar</button></div></li>)}</ul>
            {draft && <form className="followup-form" onSubmit={event => { event.preventDefault(); void save(); }}><fieldset disabled={busy}><legend>{draft.id ? 'Editar asunto' : 'Nuevo asunto local'}</legend><label>Qué quieres seguir<input autoFocus required maxLength={200} value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} placeholder="Describe el asunto con tus palabras" /></label><div className="followup-form-fields"><label>Tipo<select aria-label="Tipo del asunto" value={draft.category} onChange={event => { const value = categorySchema.safeParse(event.target.value); if (value.success) setDraft({ ...draft, category: value.data }); }}>{categorySchema.options.map(value => <option value={value} key={value}>{categories[value]}</option>)}</select></label><label>Atención<select aria-label="Atención del asunto" value={draft.attention} onChange={event => { const value = attentionSchema.safeParse(event.target.value); if (value.success) setDraft({ ...draft, attention: value.data }); }}>{attentionSchema.options.map(value => <option value={value} key={value}>{attentions[value]}</option>)}</select></label></div><p className="evidence-hint">{draft.message_ids.length ? `${draft.message_ids.length} mensajes seleccionados como evidencia.` : 'Sin selección: se vincula la conversación completa.'} Puedes seleccionar solo los mensajes que sostienen este asunto; no tienes que marcar todos.</p>{draft.message_ids.length > 0 && <button type="button" className="text-button" onClick={() => setDraft({ ...draft, message_ids: [] })}>Usar contexto completo</button>}<div className="followup-form-actions"><button type="button" className="secondary-button" onClick={() => setDraft(null)}>Cancelar</button><button className="primary-button" type="submit" disabled={!draft.title.trim()}>{busy ? 'Guardando…' : 'Guardar asunto'}</button></div></fieldset></form>}
          </section>
          <div className="context-caption"><strong>Contexto guardado, en orden cronológico</strong><span>{detail.offset + 1}–{detail.offset + detail.messages.length} de {detail.total}</span></div>
          {detail.offset > 0 && detail.conversation.root && <details className="pinned-root" open><summary>Recordar el mensaje inicial</summary><p className="message-text"><MentionText text={detail.conversation.root.text} self={detail.self_user_id} /></p></details>}
          <div className="context-timeline">{detail.messages.map(message => <ContextEntry key={message.id} message={message} self={detail.self_user_id} root={message.message_id === detail.conversation.conversation_id} draft={draft} toggle={toggle} variants={variants} />)}</div>
          <nav className="conversation-pages context-pages" aria-label="Páginas del contexto"><button disabled={busy || detail.offset === 0} onClick={conversations.previousContext}>Contexto anterior</button><span>{detail.offset + 1}–{detail.offset + detail.messages.length} de {detail.total}</span><button disabled={busy || detail.next_offset === null} onClick={() => { if (detail.next_offset !== null) conversations.setContextOffset(detail.next_offset); }}>Contexto siguiente</button></nav>
          {detail.conversation.new_count > 0 && <button className="text-button activity-seen" disabled={busy || draft !== null} onClick={() => { void conversations.markSeen(); }}>Ya vi esta actividad hasta este punto</button>}
          <p className="context-footnote">No se crean tareas por responder, agradecer o mencionar. Solo se muestra lo guardado; pueden faltar mensajes o contexto en la fuente.</p>
        </>}
      </section>
    </div>
  </section>;
}
