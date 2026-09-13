import { Fragment, useEffect, useRef, type ReactNode } from 'react';
import type { Citation } from './api';

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    plus: <path d="M12 5v14M5 12h14" />,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    arrow: <path d="M12 19V5m-6 6 6-6 6 6" />,
    chat: <path d="M20 15a3 3 0 0 1-3 3H8l-4 3V6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3z" />,
    document: <><path d="M14 3H5v18h14V8zM14 3v5h5M8 12h8M8 16h6" /></>,
    folder: <path d="M3 6h7l2 2h9v12H3z" />,
    settings: <><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="3" /><circle cx="15" cy="17" r="3" /></>,
    chevron: <path d="m9 5 7 7-7 7" />,
    trash: <><path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7" /></>,
    refresh: <><path d="M20 7v5h-5M4 17v-5h5" /><path d="M6 7a7 7 0 0 1 12-1l2 6M4 12l2 6a7 7 0 0 0 12-1" /></>,
    external: <><path d="M14 3h7v7M21 3l-11 11M10 3H3v18h18v-7" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    search: <><circle cx="10" cy="10" r="6" /><path d="m15 15 6 6" /></>,
    stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{paths[name] || paths.document}</svg>;
}

export function Dialog({ title, close, children, panel = false }: { title: string; close: () => void; children: ReactNode; panel?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = ref.current;
    dialog?.showModal();
    dialog?.querySelector<HTMLElement>('input:not([disabled]), textarea:not([disabled]), select:not([disabled])')?.focus();
    return () => { dialog?.close(); previous?.focus(); };
  }, []);
  return <dialog ref={ref} className={panel ? 'dialog drawer' : 'dialog'} aria-label={title} onCancel={event => { event.preventDefault(); close(); }} onClick={event => { if (event.target === ref.current) close(); }}>
    <header className="dialog-header"><h2>{title}</h2><button className="icon-button" onClick={close} aria-label={`Close ${title}`}><Icon name="close" /></button></header>
    {children}
  </dialog>;
}

function inline(text: string, citations: Citation[], source: (ids: number[]) => void): ReactNode[] {
  const tokens = text.split(/(\[[^\]\n]+\]|`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return tokens.map((token, index) => {
    const matches = citations.filter(c => `[${c.filename}, ${c.locator}]` === token);
    if (matches.length) return <button key={index} className="citation" title={token} onClick={() => source(matches.map(c => c.chunk_id))}>{matches[0].filename}<span>· {matches[0].locator}</span></button>;
    if (token.startsWith('`') && token.endsWith('`')) return <code key={index}>{token.slice(1, -1)}</code>;
    if (token.startsWith('**') && token.endsWith('**')) return <strong key={index}>{token.slice(2, -2)}</strong>;
    if (token.startsWith('*') && token.endsWith('*')) return <em key={index}>{token.slice(1, -1)}</em>;
    return <Fragment key={index}>{token}</Fragment>;
  });
}

export function Markdown({ text, citations, source }: { text: string; citations: Citation[]; source: (ids: number[]) => void }) {
  const lines = text.split('\n');
  const nodes: ReactNode[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) continue;
    if (line.startsWith('```')) {
      const code: string[] = [];
      while (++i < lines.length && !lines[i].startsWith('```')) code.push(lines[i]);
      nodes.push(<pre key={i}><code>{code.join('\n')}</code></pre>);
    } else if (/^#{1,6}\s/.test(line)) {
      nodes.push(<h3 key={i}>{inline(line.replace(/^#+\s/, ''), citations, source)}</h3>);
    } else if (/^\s*([-*]|\d+\.)\s/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items = [];
      do { items.push(<li key={i}>{inline(lines[i].replace(/^\s*([-*]|\d+\.)\s/, ''), citations, source)}</li>); i++; }
      while (i < lines.length && /^\s*([-*]|\d+\.)\s/.test(lines[i]));
      nodes.push(ordered ? <ol key={i}>{items}</ol> : <ul key={i}>{items}</ul>); i--;
    } else if (line.includes('|') && i + 1 < lines.length && /^\s*\|?\s*:?-{3}/.test(lines[i + 1])) {
      const cells = (row: string) => row.trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim());
      const header = cells(line); i += 2; const rows = [];
      while (i < lines.length && lines[i].includes('|')) { rows.push(cells(lines[i])); i++; }
      nodes.push(<div className="table-scroll" key={i}><table><thead><tr>{header.map((cell, j) => <th key={j}>{inline(cell, citations, source)}</th>)}</tr></thead><tbody>{rows.map((row, j) => <tr key={j}>{row.map((cell, k) => <td key={k}>{inline(cell, citations, source)}</td>)}</tr>)}</tbody></table></div>); i--;
    } else {
      const paragraph = [line];
      while (i + 1 < lines.length && lines[i + 1].trim() && !/^(#|```|\s*[-*]\s|\s*\d+\.\s)/.test(lines[i + 1]) && !lines[i + 1].includes('|')) paragraph.push(lines[++i]);
      nodes.push(<p key={i}>{inline(paragraph.join('\n'), citations, source)}</p>);
    }
  }
  return <div className="markdown">{nodes}</div>;
}
