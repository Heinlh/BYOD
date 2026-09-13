import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Document, type Job, type Settings, type Source, type Workspace } from './api';
import { Dialog, Icon } from './components';

const failure = (error: unknown) => error instanceof Error ? error.message : 'Operation failed. Retry.';
export const providerLabel = (name: string) => ({ openai: 'OpenAI', anthropic: 'Anthropic', ollama: 'Ollama' })[name] || name;

export function WorkspaceForm({ close, created }: { close: () => void; created: (id: number) => void | Promise<void> }) {
  const [name, setName] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { const result = await api<Workspace>('/workspaces', 'POST', { name }); await created(result.id); close(); }
    catch (error) { setError(failure(error)); } finally { setBusy(false); }
  }
  return <Dialog title="New workspace" close={close}><form className="dialog-body stack" onSubmit={submit}>
    <label>Workspace name<input autoFocus value={name} onChange={event => setName(event.target.value)} maxLength={200} placeholder="Course name" required /></label>
    {error && <p className="error" role="alert">{error}</p>}
    <div className="actions"><button type="button" className="button secondary" onClick={close}>Cancel</button><button className="button primary" disabled={busy || !name.trim()}>Create workspace</button></div>
  </form></Dialog>;
}

export function DocumentPanel({ workspace, close, jobs, trackJob, removeWorkspace }: {
  workspace: Workspace; close: () => void; jobs: string[]; trackJob: (id: string) => void; removeWorkspace: () => void;
}) {
  const queryClient = useQueryClient();
  const documents = useQuery({ queryKey: ['documents', workspace.id], queryFn: () => api<Document[]>(`/workspaces/${workspace.id}/documents`), refetchInterval: query => query.state.data?.some(d => d.status === 'pending') ? 1000 : false });
  const progress = useQueries({ queries: jobs.map(id => ({ queryKey: ['job', id], queryFn: () => api<Job>(`/jobs/${id}`), refetchInterval: (query: { state: { data: Job | undefined } }) => ['done', 'failed'].includes(query.state.data?.state || '') ? false as const : 1000 })) });
  const [adding, setAdding] = useState<'files' | 'folder' | null>(null), [paths, setPaths] = useState('');
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState<Document | null>(null);
  const signature = progress.map(p => p.data?.state).join(',');
  useEffect(() => { void queryClient.invalidateQueries({ queryKey: ['documents', workspace.id] }); void queryClient.invalidateQueries({ queryKey: ['workspaces'] }); void queryClient.invalidateQueries({ queryKey: ['settings'] }); }, [signature, queryClient, workspace.id]);
  async function action(operation: () => Promise<void>) {
    setBusy(true); setError(''); try { await operation(); } catch (error) { setError(failure(error)); } finally { setBusy(false); }
  }
  async function add(event: FormEvent) {
    event.preventDefault(); await action(async () => {
      const result = await api<{ job_id: string }>(`/workspaces/${workspace.id}/documents`, 'POST', { paths: paths.split('\n').map(p => p.trim().replace(/^["']|["']$/g, '')).filter(Boolean) });
      trackJob(result.job_id); setPaths(''); setAdding(null);
    });
  }
  async function reindex(id: number) { await action(async () => { const result = await api<{ job_id: string }>(`/documents/${id}/reindex`, 'POST'); trackJob(result.job_id); }); }
  return <Dialog title="Documents" close={close} panel>
    <div className="drawer-context"><span className="eyebrow">WORKSPACE</span><h3>{workspace.name}</h3><span className="muted">{documents.data?.length || 0} documents</span></div>
    <div className="document-actions"><button className="button secondary" onClick={() => setAdding('files')}><Icon name="plus" />Add files</button><button className="button secondary" onClick={() => setAdding('folder')}><Icon name="folder" />Add folder</button></div>
    {adding && <form className="path-form stack" onSubmit={add}>
      <label>{adding === 'files' ? 'File paths, one per line' : 'Folder path'}<textarea autoFocus rows={adding === 'files' ? 3 : 2} value={paths} onChange={event => setPaths(event.target.value)} placeholder={adding === 'files' ? 'Paste full file paths' : 'Paste the full folder path'} required /></label>
      <p className="muted small">PDF, DOCX, and PPTX. Files stay in their original location.</p>
      <div className="actions"><button type="button" className="text-button" onClick={() => setAdding(null)}>Cancel</button><button className="button primary" disabled={busy || !paths.trim()}>Add documents</button></div>
    </form>}
    {progress.map((item, index) => item.data && <div key={jobs[index]} className="job-status" role="status">
      <div className="split"><span>{item.data.state === 'done' ? 'Indexing complete' : item.data.state === 'failed' ? 'Indexing finished with errors' : 'Indexing documents'}</span><span className="muted">{item.data.completed + item.data.failed}/{item.data.total}</span></div>
      {!['done', 'failed'].includes(item.data.state) && <><progress max={item.data.total || 1} value={item.data.completed + item.data.failed} /><p className="muted small truncate">{item.data.current_file || 'Preparing files…'}</p>{item.data.download && item.data.download.completed < item.data.download.total && <p className="muted small">Downloading local embedding model…</p>}</>}
      {item.data.skipped > 0 && <p className="muted small">{item.data.skipped} already indexed</p>}
      {item.data.errors.map((error, i) => <p className="error small" key={i}>{error.filename}: {error.message}</p>)}
    </div>)}
    {(error || documents.error) && <p className="error panel-error" role="alert">{error || failure(documents.error)}</p>}
    <div className="document-list">
      {documents.isLoading && <p className="muted">Loading documents…</p>}
      {documents.data?.length === 0 && <p className="muted empty-documents">No documents</p>}
      {documents.data?.map(doc => <article className="document-row" key={doc.id}>
        <div className="file-icon"><Icon name="document" size={23} /><span>{doc.doc_type.toUpperCase()}</span></div>
        <div className="file-details"><h4 title={doc.filename}>{doc.filename}</h4><p className="muted small">{doc.unit_count !== null ? `${doc.unit_count} ${doc.doc_type === 'pptx' ? 'slides' : 'pages'} · ` : ''}{doc.chunk_count} chunks</p><span className={`status ${doc.status}`}><span />{({ indexed: 'Indexed', pending: 'Indexing', missing: 'File missing', failed: 'Failed' })[doc.status]}</span>{doc.error && <p className="error small">{doc.error}</p>}{doc.status === 'missing' && <p className="error small">File moved or deleted. Re-add it.</p>}</div>
        <div className="file-actions"><button className="icon-button" disabled={busy} title="Re-index" aria-label={`Re-index ${doc.filename}`} onClick={() => void reindex(doc.id)}><Icon name="refresh" size={15} /></button><button className="icon-button" title="Remove document" aria-label={`Remove ${doc.filename}`} onClick={() => setRemoving(doc)}><Icon name="trash" size={15} /></button></div>
      </article>)}
    </div>
    <footer className="drawer-footer"><span className="small muted">Local source files</span><button className="text-button danger" onClick={removeWorkspace}>Remove workspace</button></footer>
    {removing && <Dialog title="Remove document" close={() => setRemoving(null)}><div className="dialog-body stack"><p>Remove {removing.filename} and its indexed content? The source file stays in place.</p><div className="actions"><button className="button secondary" onClick={() => setRemoving(null)}>Cancel</button><button className="button danger-button" disabled={busy} onClick={() => void action(async () => { await api(`/documents/${removing.id}`, 'DELETE'); setRemoving(null); await queryClient.invalidateQueries({ queryKey: ['documents', workspace.id] }); await queryClient.invalidateQueries({ queryKey: ['workspaces'] }); })}>Remove document</button></div></div></Dialog>}
  </Dialog>;
}

export function SettingsPanel({ workspaceId, close, trackJob }: { workspaceId: number | null; close: () => void; trackJob: (id: string) => void }) {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ['settings', workspaceId], queryFn: () => api<Settings>(`/settings${workspaceId ? `?workspace_id=${workspaceId}` : ''}`) });
  const [provider, setProvider] = useState(''), [model, setModel] = useState(''), [score, setScore] = useState('0.70');
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false);
  const keyForm = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (settings.data && !provider) {
      const selected = settings.data.active.provider || settings.data.providers.find(p => p.name === 'ollama' && p.available)?.name || 'openai';
      setProvider(selected); setModel(settings.data.active.model || settings.data.providers.find(p => p.name === selected)?.models[0] || '');
      setScore(String(settings.data.retrieval_min_score));
    }
  }, [settings.data, provider]);
  const selected = settings.data?.providers.find(p => p.name === provider);
  async function action(operation: () => Promise<void>) { setBusy(true); setError(''); setNotice(''); try { await operation(); } catch (error) { setError(failure(error)); } finally { setBusy(false); } }
  async function saveKey(event: FormEvent) {
    event.preventDefault();
    const secret = new FormData(event.currentTarget as HTMLFormElement).get('key');
    keyForm.current?.reset(); // Key never enters React/Zustand state or browser persistence.
    await action(async () => {
      const result = await api<{ valid: boolean }>('/settings/key', 'PUT', { provider, key: secret });
      if (!result.valid) throw new Error('Key validation failed. Check the key and provider access, then retry.');
      setNotice('Key saved to the OS keychain.'); await queryClient.invalidateQueries({ queryKey: ['settings'] });
    });
  }
  async function save(event: FormEvent) {
    event.preventDefault(); await action(async () => {
      await api('/settings', 'PUT', { provider, model, workspace_id: workspaceId, retrieval_min_score: Number(score) });
      await queryClient.invalidateQueries({ queryKey: ['settings'] }); setNotice('Settings saved.');
    });
  }
  return <Dialog title="Settings" close={close}><div className="dialog-body settings-body stack">
    <span className="eyebrow">REASONING PROVIDER</span>
    <div className="provider-options">{settings.data?.providers.filter(p => p.available).map(p => <button key={p.name} className={`provider-option ${provider === p.name ? 'selected' : ''}`} aria-pressed={provider === p.name} onClick={() => { setProvider(p.name); setModel(p.models[0] || ''); setNotice(''); }}><span>{providerLabel(p.name)}</span><span className="small muted">{p.name === 'ollama' ? 'Local' : p.configured ? 'Key configured' : 'Key required'}</span></button>)}</div>
    {provider && provider !== 'ollama' && <form ref={keyForm} onSubmit={saveKey} className="key-form stack">
      <label>API key<input type="password" name="key" autoComplete="off" placeholder={selected?.configured ? 'Enter a replacement key' : 'Enter your provider API key'} required maxLength={4096} /></label>
      <div className="split"><span className="small muted">Stored in your OS keychain</span><div className="actions">{selected?.configured && <button type="button" className="text-button danger" onClick={() => void action(async () => { await api(`/settings/key/${provider}`, 'DELETE'); await queryClient.invalidateQueries({ queryKey: ['settings'] }); setNotice('Key removed.'); })}>Remove key</button>}<button className="button secondary" disabled={busy}>Validate & save key</button></div></div>
    </form>}
    <form onSubmit={save} className="stack">
      <label>Model<select value={model} onChange={event => setModel(event.target.value)}><option value="" disabled>Select a model</option>{selected?.models.map(m => <option key={m}>{m}</option>)}</select></label>
      <div className="setting-divider" />
      <div className="split"><div><span className="eyebrow">LOCAL EMBEDDINGS</span><p className="small model-name">{settings.data?.embed_model || 'Loading…'}</p></div><span className="local-badge">ON DEVICE</span></div>
      {settings.data?.stale_index && <div className="warning stack"><p>The embedding model changed. Re-index to use these documents.</p><button type="button" className="button secondary" disabled={!workspaceId || busy} onClick={() => void action(async () => {
        const docs = await api<Document[]>(`/workspaces/${workspaceId}/documents`);
        for (const doc of docs) { const job = await api<{ job_id: string }>(`/documents/${doc.id}/reindex`, 'POST'); trackJob(job.job_id); }
        setNotice('Re-indexing started. View progress in Documents.');
      })}>Re-index workspace</button></div>}
      <details><summary>Source relevance</summary><label className="relevance-label">Minimum match score<input type="number" min="0" max="1" step="0.01" value={score} onChange={event => setScore(event.target.value)} required /></label><p className="small muted">Higher values require a closer match. Default: 0.70.</p></details>
      <div><span className="eyebrow">DATA LOCATION</span><p className="data-path">{settings.data?.data_dir}</p><button type="button" className="text-button" onClick={() => void action(async () => { await api('/settings/reveal', 'POST'); })}><Icon name="folder" size={14} />Reveal in file manager</button></div>
      {(error || settings.error) && <p className="error" role="alert">{error || failure(settings.error)}</p>}{notice && <p className="notice" role="status">{notice}</p>}
      <div className="actions"><button type="button" className="button secondary" onClick={close}>Close</button><button className="button primary" disabled={busy || !model}>Save settings</button></div>
    </form>
  </div></Dialog>;
}

export function SourcePanel({ ids, close }: { ids: number[]; close: () => void }) {
  const [index, setIndex] = useState(0), [error, setError] = useState('');
  const source = useQuery({ queryKey: ['source', ids[index]], queryFn: () => api<Source>(`/chunks/${ids[index]}`) });
  return <Dialog title="Source" close={close} panel><div className="source-body">
    {source.data && <><div className="source-heading"><span className="eyebrow">DOCUMENT EXCERPT</span><h3>{source.data.filename}</h3><span className="locator-label">{source.data.locator}</span></div><pre className="source-text">{source.data.text}</pre><button className="button secondary" onClick={() => { void api(`/documents/${source.data!.document_id}/open`, 'POST').catch(e => setError(failure(e))); }}><Icon name="external" size={15} />Open source file</button></>}
    {source.isLoading && <p className="muted">Loading source…</p>}{(source.error || error) && <p className="error" role="alert">{error || failure(source.error)}</p>}
    {ids.length > 1 && <div className="source-navigation"><button className="button secondary" disabled={index === 0} onClick={() => setIndex(index - 1)}>Previous</button><span className="muted">{index + 1} of {ids.length}</span><button className="button secondary" disabled={index === ids.length - 1} onClick={() => setIndex(index + 1)}>Next</button></div>}
  </div></Dialog>;
}
