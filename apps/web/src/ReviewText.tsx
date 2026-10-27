import { Fragment, useState } from 'react';
import type { ReactNode } from 'react';

const LANGUAGES: Record<string, string> = {
  py: 'Python', python: 'Python', ts: 'TypeScript', tsx: 'TypeScript',
  typescript: 'TypeScript', js: 'JavaScript', javascript: 'JavaScript',
  json: 'JSON', sql: 'SQL', diff: 'Diff', bash: 'Shell', sh: 'Shell',
  md: 'Markdown', markdown: 'Markdown', text: 'Texto',
};
const TOKENS = /("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:class|def|return|from|import|if|else|elif|for|in|None|True|False|const|let|function|async|await|export|type|interface|new|null|true|false|SELECT|FROM|WHERE|AND|OR)\b|\b\d+(?:\.\d+)?\b|(?:#|\/\/).*$)/g;

function syntax(line: string) {
  return line.split(TOKENS).map((part, index) => {
    if (index % 2 === 0) return part;
    const tone = part.startsWith('#') || part.startsWith('//') ? 'comment'
      : part.startsWith('"') || part.startsWith("'") ? 'string'
      : /^\d/.test(part) ? 'number' : 'keyword';
    return <span className={`review-token-${tone}`} key={index}>{part}</span>;
  });
}

export function CodeBlock({ text, language = 'text', label }: { text: string; language?: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);
  const name = LANGUAGES[language] || language.slice(0, 24);
  async function copy() {
    try { await navigator.clipboard.writeText(text); setCopied(true); setError(false); }
    catch { setError(true); }
  }
  return <figure className="review-code">
    <figcaption><span>{label && <strong>{label}</strong>}<span>{name}</span></span>
      <button type="button" onClick={() => { void copy(); }}>{copied ? 'Copiado' : 'Copiar código'}</button>
    </figcaption>
    <pre tabIndex={0} aria-label={`Código, ${name}`}><code>{text.split('\n').map((line, index) => {
      const change = language === 'diff' ? line.startsWith('+') && !line.startsWith('+++') ? 'added'
        : line.startsWith('-') && !line.startsWith('---') ? 'removed'
        : line.startsWith('@@') ? 'hunk' : undefined : undefined;
      return <span className="review-code-line" data-change={change} key={index}>{line ? syntax(line) : '\u200b'}</span>;
    })}</code></pre>
    {error && <p role="status">No se pudo copiar. Puedes seleccionar el código.</p>}
  </figure>;
}

function Inline({ text }: { text: string }) {
  return <>{text.split(/(`[^`\n]+`|\*\*[^*\n]+\*\*)/g).map((part, index) =>
    part.startsWith('`') && part.endsWith('`') ? <code key={index}>{part.slice(1, -1)}</code>
      : part.startsWith('**') && part.endsWith('**') ? <strong key={index}><Inline text={part.slice(2, -2)} /></strong>
      : <Fragment key={index}>{part}</Fragment>)}</>;
}

export function ReviewText({ text }: { text: string }) {
  const lines = text.split('\n');
  const blocks: ReactNode[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    const key = index;
    const fence = /^\s{0,3}```([\w+-]*)\s*$/.exec(line);
    if (fence) {
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !/^\s{0,3}```\s*$/.test(lines[index])) body.push(lines[index++]);
      if (index < lines.length) index += 1;
      blocks.push(<CodeBlock key={key} text={body.join('\n')} language={fence[1] || 'text'} />);
    } else if (/^\s*[-*] /.test(line) || /^\s*\d+\. /.test(line)) {
      const ordered = /^\s*\d+\. /.test(line);
      const pattern = ordered ? /^\s*\d+\. / : /^\s*[-*] /;
      const items: ReactNode[] = [];
      while (index < lines.length && pattern.test(lines[index])) {
        items.push(<li key={index}><Inline text={lines[index].replace(pattern, '')} /></li>);
        index += 1;
      }
      blocks.push(ordered ? <ol key={key} start={Number.parseInt(line, 10)}>{items}</ol> : <ul key={key}>{items}</ul>);
    } else if (!line.trim()) {
      index += 1;
    } else if (/^#{1,4} /.test(line)) {
      blocks.push(<h5 key={key}><Inline text={line.replace(/^#{1,4} /, '')} /></h5>);
      index += 1;
    } else {
      const body = [line];
      index += 1;
      while (index < lines.length && lines[index].trim() && !/^\s*(?:```|[-*] |\d+\. |#{1,4} )/.test(lines[index])) body.push(lines[index++]);
      blocks.push(<p key={key}><Inline text={body.join('\n')} /></p>);
    }
  }
  return <div className="review-rich-text">{blocks}</div>;
}
