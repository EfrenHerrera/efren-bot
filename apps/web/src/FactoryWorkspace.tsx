import { useState } from 'react';
import { effectLabels, jobLabels, riskLabels } from '@/factory-client';
import type { FactoryEffect, FactoryItem, FactoryJob } from '@/factory-client';
import { useFactory } from '@/use-factory';
import '@/factory.css';

type Plant = ReturnType<typeof useFactory>;

function Awaiting({ item, plant, projects }: { item: FactoryItem; plant: Plant; projects: string[] }) {
  const [project, setProject] = useState(item.admission?.project || projects[0] || '');
  const disabled = plant.busy || Boolean(plant.error);
  return <article className="factory-card"><header><strong>{item.title || item.external_id}</strong><span className="pill muted">{item.source}</span></header>
    <p className="message-text">{item.text}</p>
    <ul className="factory-reasons">{item.admission?.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
    <div className="human-controls">
      <label>Proyecto<select value={project} onChange={event => setProject(event.target.value)}>{projects.map(name => <option key={name} value={name}>{name}</option>)}</select></label>
      <button className="primary-button" disabled={disabled || !project} onClick={() => { if (window.confirm(`Admitir en «${project}» y encolar el trabajo.\n\n${item.text}`)) void plant.admit(item.id, project); }}>Admitir</button>
      <button className="text-button" disabled={disabled} onClick={() => { void plant.discard(item.id); }}>Descartar</button></div></article>;
}

function JobRow({ job, plant }: { job: FactoryJob; plant: Plant }) {
  const [text, setText] = useState('');
  const disabled = plant.busy || Boolean(plant.error);
  const live = ['queued', 'running', 'paused'].includes(job.status);
  return <li className="factory-job"><div><strong>{job.project}</strong><span className={`pill ${job.status === 'succeeded' ? 'succeeded' : job.status === 'failed' || job.status === 'blocked' ? 'failed' : 'muted'}`}>{jobLabels[job.status] || job.status}</span>{job.risk && <span className="pill muted">{riskLabels[job.risk] || job.risk}</span>}{job.review && <span className="pill muted">Revisión: {job.review}</span>}</div>
    {job.branch && <p className="human-destination">Rama {job.branch}</p>}
    {job.checks.length > 0 && <p className="review-help">{job.checks.map(check => `${check.name}: ${check.status}`).join(' · ')}</p>}
    {job.human_reasons.length > 0 && <details><summary>Por qué necesita a una persona · {job.human_reasons.length}</summary><ul>{job.human_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></details>}
    {live && <div className="human-controls">
      <button className="secondary-button" disabled={disabled || job.status !== 'queued'} onClick={() => { void plant.control(job.id, 'pause'); }}>Pausar</button>
      <button className="secondary-button" disabled={disabled || job.status !== 'paused'} onClick={() => { void plant.control(job.id, 'continue'); }}>Continuar</button>
      <button className="text-button" disabled={disabled} onClick={() => { if (window.confirm(`Detener el trabajo de ${job.project}.`)) void plant.control(job.id, 'stop'); }}>Detener</button>
      <input aria-label="Nuevo enfoque" placeholder="Reorientar: escribe la corrección" maxLength={4000} value={text} onChange={event => setText(event.target.value)} />
      <button className="secondary-button" disabled={disabled || !text.trim()} onClick={() => { void plant.control(job.id, 'redirect', text).then(done => { if (done) setText(''); }); }}>Reorientar</button></div>}
  </li>;
}

function EffectCard({ effect, plant }: { effect: FactoryEffect; plant: Plant }) {
  const disabled = plant.busy || Boolean(plant.error);
  const exact = JSON.stringify(effect.payload, null, 2);
  return <article className="factory-card"><header><strong>{effectLabels[effect.kind] || effect.kind}</strong><span>Necesita tu aprobación</span></header>
    <details open><summary>Contenido exacto que se aprobará</summary><pre className="factory-payload">{exact}</pre></details>
    <p className="review-help">Aprobar solo esta versión. Si cambia, la aprobación deja de aplicar. Vence {new Date(effect.expires_at).toLocaleString('es-MX')}.</p>
    <div className="human-controls"><button className="primary-button" disabled={disabled} onClick={() => { if (window.confirm(`Aprobar y ejecutar SOLO esta acción:\n\n${effectLabels[effect.kind] || effect.kind}\n\n${exact}`)) void plant.decide(effect.id, 'approve', effect.fingerprint); }}>Aprobar esta acción</button>
      <button className="secondary-button" disabled={disabled} onClick={() => { void plant.decide(effect.id, 'deny', effect.fingerprint); }}>Denegar</button></div></article>;
}

export function FactoryWorkspace() {
  const plant = useFactory();
  const data = plant.data;
  const projects = data?.projects.map(project => project.name) || [];
  return <section className="review-workspace factory-workspace" aria-label="Fábrica">
    <header className="review-heading"><div><h2>Fábrica</h2><p>Entra cualquier fuente; aquí decides qué se admite, qué sigue y qué se publica.</p></div><button className="secondary-button" onClick={plant.refresh}>Actualizar</button></header>
    <p className="review-help">Nada se publica sin que apruebes el contenido exacto. Fusionar y desplegar no existen en la fábrica.</p>
    {plant.error && <p className="error-banner" role="alert">{plant.error}<button className="text-button" onClick={plant.refresh}>Actualizar estado</button></p>}
    <h3>Por admitir · {data?.awaiting_admission.length || 0}</h3>
    {data?.awaiting_admission.map(item => <Awaiting key={item.id} item={item} plant={plant} projects={projects} />)}
    {data && !data.awaiting_admission.length && <p className="review-help">No hay solicitudes esperando decisión.</p>}
    <h3>Acciones por aprobar · {data?.pending_effects.length || 0}</h3>
    {data?.pending_effects.map(effect => <EffectCard key={effect.id} effect={effect} plant={plant} />)}
    <h3>Trabajos · {data?.jobs.length || 0}</h3>
    <ul className="factory-jobs">{data?.jobs.map(job => <JobRow key={job.id} job={job} plant={plant} />)}</ul>
    {!data && !plant.error && <p role="status">Conectando…</p>}
  </section>;
}
