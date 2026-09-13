import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, streamChat, type Chat, type Citation, type Document, type Message, type Settings, type Workspace } from './api';
import { Dialog, Icon, Markdown } from './components';
import { DocumentPanel, SettingsPanel, SourcePanel, WorkspaceForm, providerLabel } from './panels';
import { useUI } from './store';

export function App() {
  const { workspaceId, chatId, panel, selectWorkspace, selectChat, setPanel } = useUI();
  const queryClient = useQueryClient();
  const workspaces = useQuery({ queryKey: ['workspaces'], queryFn: () => api<Workspace[]>('/workspaces') });
  const chats = useQuery({ queryKey: ['chats', workspaceId], queryFn: () => api<Chat[]>(`/workspaces/${workspaceId}/chats`), enabled: workspaceId !== null });
  const documents = useQuery({ queryKey: ['documents', workspaceId], queryFn: () => api<Document[]>(`/workspaces/${workspaceId}/documents`), enabled: workspaceId !== null });
  const history = useQuery({ queryKey: ['messages', chatId], queryFn: () => api<Message[]>(`/chats/${chatId}/messages`), enabled: chatId !== null });
  const settings = useQuery({ queryKey: ['settings', workspaceId], queryFn: () => api<Settings>(`/settings${workspaceId ? `?workspace_id=${workspaceId}` : ''}`) });
  const workspace = workspaces.data?.find(w => w.id === workspaceId);
  const [creating, setCreating] = useState(false), [switcher, setSwitcher] = useState(false), [filter, setFilter] = useState('');
  const [sourceIds, setSourceIds] = useState<number[] | null>(null), [scope, setScope] = useState('');
  const [draft, setDraft] = useState(''), [error, setError] = useState(''), [streaming, setStreaming] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState(''), [answer, setAnswer] = useState(''), [sources, setSources] = useState<Citation[]>([]);
  const [jobMap, setJobMap] = useState<Record<number, string[]>>({});
  const [remove, setRemove] = useState<{ kind: 'workspace' | 'chat'; id: number; name: string } | null>(null);
  const controller = useRef<AbortController | null>(null), buffer = useRef('');
  const thread = useRef<HTMLDivElement>(null), textarea = useRef<HTMLTextAreaElement>(null), atBottom = useRef(true);
  const selectedProvider = settings.data?.providers.find(p => p.name === settings.data.active.provider);
  const canSend = Boolean(workspace && draft.trim() && !streaming);

  useEffect(() => { if (workspaces.data && !workspaces.data.some(w => w.id === workspaceId)) selectWorkspace(workspaces.data[0]?.id ?? null); }, [workspaceId, workspaces.data, selectWorkspace]);
  useEffect(() => { if (scope && documents.data && !documents.data.some(d => String(d.id) === scope && d.status === 'indexed')) setScope(''); }, [scope, documents.data]);
  useEffect(() => { if (atBottom.current && thread.current) thread.current.scrollTop = thread.current.scrollHeight; }, [answer, pendingQuestion, history.data]);
  useEffect(() => () => controller.current?.abort(), []);
  function resetStream() { controller.current?.abort(); controller.current = null; setStreaming(false); setPendingQuestion(''); setAnswer(''); setSources([]); buffer.current = ''; }
  function chooseWorkspace(id: number) { resetStream(); selectWorkspace(id); setScope(''); setDraft(''); setError(''); setSwitcher(false); atBottom.current = true; }
  function chooseChat(id: number | null) { resetStream(); selectChat(id); setDraft(''); setError(''); atBottom.current = true; }
  async function newChat() {
    if (!workspaceId) return;
    try { const result = await api<{ id: number }>(`/workspaces/${workspaceId}/chats`, 'POST'); chooseChat(result.id); await queryClient.invalidateQueries({ queryKey: ['chats', workspaceId] }); textarea.current?.focus(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not create chat. Retry.'); }
  }
  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if (!(event.ctrlKey || event.metaKey)) return;
      if (event.key.toLowerCase() === 'k') { event.preventDefault(); setSwitcher(true); setFilter(''); }
      if (event.key.toLowerCase() === 'n' && !document.querySelector('dialog[open]')) { event.preventDefault(); void newChat(); }
    }
    window.addEventListener('keydown', shortcut); return () => window.removeEventListener('keydown', shortcut);
  });
  function trackJob(id: string) { if (workspaceId) setJobMap(previous => ({ ...previous, [workspaceId]: [...(previous[workspaceId] || []), id] })); }
  async function send(event?: FormEvent) {
    event?.preventDefault(); if (!canSend || !workspaceId) return;
    const currentWorkspace = workspaceId, question = draft.trim();
    const abort = new AbortController(); controller.current = abort;
    setStreaming(true); setError(''); setDraft(''); setAnswer(''); setSources([]); setPendingQuestion(question); buffer.current = ''; atBottom.current = true;
    const refresh = window.setInterval(() => { if (controller.current === abort) setAnswer(buffer.current); }, 50);
    let currentChat = chatId;
    try {
      if (currentChat === null) { const result = await api<{ id: number }>(`/workspaces/${currentWorkspace}/chats`, 'POST'); currentChat = result.id; if (abort.signal.aborted) return; selectChat(currentChat); }
      await streamChat(currentChat, question, scope ? [Number(scope)] : undefined, abort.signal,
        token => { buffer.current += token; }, values => { if (!abort.signal.aborted) setSources(values); });
      await queryClient.invalidateQueries({ queryKey: ['messages', currentChat] });
    } catch (e) {
      if (!abort.signal.aborted) { setError(e instanceof Error ? e.message : 'Could not finish the reply. Retry.'); setDraft(question); }
    } finally {
      window.clearInterval(refresh);
      if (currentChat !== null) await queryClient.invalidateQueries({ queryKey: ['messages', currentChat] });
      await queryClient.invalidateQueries({ queryKey: ['chats', currentWorkspace] });
      if (controller.current === abort) { setStreaming(false); setPendingQuestion(''); setAnswer(''); setSources([]); controller.current = null; textarea.current?.focus(); }
    }
  }
  async function changeModel(value: string) {
    if (value === 'settings') { setPanel('settings'); return; }
    const slash = value.indexOf('/');
    try { await api('/settings', 'PUT', { workspace_id: workspaceId, provider: value.slice(0, slash), model: value.slice(slash + 1) }); await queryClient.invalidateQueries({ queryKey: ['settings'] }); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not change model. Check Settings.'); }
  }
  async function confirmRemove() {
    if (!remove) return;
    try {
      await api(`/${remove.kind === 'workspace' ? 'workspaces' : 'chats'}/${remove.id}`, 'DELETE');
      if (remove.kind === 'workspace') {
        const remaining = (workspaces.data || []).filter(w => w.id !== remove.id);
        const position = (workspaces.data || []).findIndex(w => w.id === remove.id);
        resetStream(); setScope(''); setPanel(null);
        queryClient.setQueryData(['workspaces'], remaining);
        selectWorkspace(remaining[Math.max(0, position - 1)]?.id ?? null);
        await queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      }
      else { if (remove.id === chatId) chooseChat(null); await queryClient.invalidateQueries({ queryKey: ['chats', workspaceId] }); }
      setRemove(null);
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not remove item. Retry.'); }
  }
  const visibleHistory = history.data || [];
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Icon name="document" size={23} /></span><span>BYOD</span><span className="brand-version">v1</span></div>
      <button className="workspace-search" onClick={() => { setSwitcher(true); setFilter(''); }}><Icon name="search" size={15} /><span>Workspaces</span><kbd>Ctrl K</kbd></button>
      <div className="sidebar-heading"><span>WORKSPACES</span><button className="icon-button" onClick={() => setCreating(true)} aria-label="New workspace"><Icon name="plus" size={16} /></button></div>
      <nav className="workspace-list" aria-label="Workspaces">{workspaces.data?.map((item, index) => <button key={item.id} className={`workspace-item ${workspaceId === item.id ? 'active' : ''}`} onClick={() => chooseWorkspace(item.id)} aria-current={workspaceId === item.id ? 'page' : undefined}><span className={`workspace-dot color-${index % 4}`} /><span className="truncate">{item.name}</span><span className="workspace-count">{item.document_count}</span></button>)}</nav>
      {workspaces.data?.length === 0 && <button className="empty-workspace-button" onClick={() => setCreating(true)}><Icon name="plus" size={15} />Create workspace</button>}
      <div className="sidebar-heading chat-heading"><span>CHATS</span><button className="icon-button" disabled={!workspaceId} onClick={() => void newChat()} aria-label="New chat" title="New chat · Ctrl N"><Icon name="plus" size={16} /></button></div>
      <nav className="chat-list" aria-label="Chats">{chats.data?.map(chat => <div key={chat.id} className={`chat-item ${chat.id === chatId ? 'active' : ''}`}><button className="chat-select" onClick={() => chooseChat(chat.id)}><Icon name="chat" size={14} /><span className="truncate">{chat.title}</span></button><button className="icon-button chat-remove" aria-label={`Delete chat ${chat.title}`} onClick={() => setRemove({ kind: 'chat', id: chat.id, name: chat.title })}><Icon name="trash" size={13} /></button></div>)}</nav>
      <footer className="sidebar-footer"><button onClick={() => setPanel('settings')}><Icon name="settings" /><span>Settings</span></button><span className="local-status"><span />Local library</span></footer>
    </aside>
    <main className="main-column">
      <header className="topbar"><div className="breadcrumb"><span>{workspace?.name || 'BYOD'}</span>{workspace && <><Icon name="chevron" size={13} /><select aria-label="Document scope" value={scope} onChange={event => setScope(event.target.value)}><option value="">All documents</option>{documents.data?.filter(d => d.status === 'indexed').map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}</select></>}</div><button className="documents-button" disabled={!workspace} onClick={() => setPanel('documents')}><Icon name="document" size={16} /><span>Documents</span><span className="count-pill">{workspace?.document_count || 0}</span></button></header>
      <div className="thread" ref={thread} onScroll={() => { if (thread.current) atBottom.current = thread.current.scrollHeight - thread.current.scrollTop - thread.current.clientHeight < 120; }}>
        {visibleHistory.length === 0 && !pendingQuestion ? <div className="empty-thread"><h1>{workspace?.name || 'No workspace selected'}</h1>{workspace && <p>{workspace.document_count} {workspace.document_count === 1 ? 'document' : 'documents'}</p>}</div> : <div className="reading-width messages">
          {visibleHistory.map(message => <article key={message.id} className={`message ${message.role}`}><div className="message-label">{message.role === 'user' ? 'YOU' : 'BYOD'}</div>{message.role === 'assistant' ? <Markdown text={message.content} citations={message.citations} source={setSourceIds} /> : <p className="user-content">{message.content}</p>}</article>)}
          {pendingQuestion && <article className="message user"><div className="message-label">YOU</div><p className="user-content">{pendingQuestion}</p></article>}
          {streaming && <article className="message assistant pending-answer"><div className="message-label">BYOD<span className="thinking-dot" /><span className="generating" role="status">{answer ? 'Writing' : 'Reading documents'}</span></div>{answer ? <Markdown text={answer} citations={sources} source={setSourceIds} /> : <div className="loading-lines" aria-hidden="true"><span /><span /></div>}{sources.length > 0 && <div className="live-sources"><button className="text-button" onClick={() => setSourceIds(sources.map(s => s.chunk_id))}>{sources.length} sources retrieved<Icon name="chevron" size={12} /></button></div>}</article>}
        </div>}
      </div>
      <div className="composer-area"><div className="reading-width">
        {(error || workspaces.error || history.error || settings.error) && <p className="error composer-error" role="alert">{error || 'Could not load the workspace. Check that BYOD is running and refresh.'}</p>}
        {settings.data?.stale_index && <p className="warning small">The embedding model changed. <button className="text-button" onClick={() => setPanel('settings')}>Re-index in Settings</button></p>}
        <form className={`composer ${streaming ? 'streaming' : ''}`} onSubmit={event => void send(event)}>
          <textarea ref={textarea} aria-label="Question" rows={2} value={draft} onChange={event => setDraft(event.target.value)} disabled={!workspace} placeholder={workspace ? 'Ask about your documents…' : 'Select a workspace'} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(); } }} />
          <div className="composer-toolbar"><div className="model-picker"><span className={`provider-dot ${selectedProvider?.configured ? 'configured' : ''}`} /><select aria-label="Model" disabled={streaming} value={settings.data?.active.provider && settings.data.active.model ? `${settings.data.active.provider}/${settings.data.active.model}` : ''} onChange={event => void changeModel(event.target.value)}><option value="" disabled>Select model</option>{settings.data?.providers.filter(p => p.available).map(p => <optgroup key={p.name} label={providerLabel(p.name)}>{p.models.map(m => <option key={m} value={`${p.name}/${m}`}>{m}</option>)}</optgroup>)}<option value="settings">Configure providers…</option></select></div>{streaming ? <button type="button" className="send-button" aria-label="Stop reply" onClick={() => controller.current?.abort()}><Icon name="stop" size={16} /></button> : <button className="send-button" disabled={!canSend} aria-label="Send question"><Icon name="arrow" size={18} /></button>}</div>
        </form><div className="composer-caption"><span>{scope ? 'Searching selected document' : workspace ? `Searching ${workspace.name}` : 'Bring Your Own Documents'}</span><span>Enter to send · Shift Enter for a new line</span></div>
      </div></div>
    </main>
    {creating && <WorkspaceForm close={() => setCreating(false)} created={async id => { await queryClient.invalidateQueries({ queryKey: ['workspaces'] }); chooseWorkspace(id); }} />}
    {switcher && <Dialog title="Switch workspace" close={() => setSwitcher(false)}><div className="dialog-body stack"><input aria-label="Find workspace" autoFocus placeholder="Find workspace" value={filter} onChange={event => setFilter(event.target.value)} /><div className="switcher-list">{workspaces.data?.filter(w => w.name.toLowerCase().includes(filter.toLowerCase())).map(w => <button key={w.id} onClick={() => chooseWorkspace(w.id)}><Icon name="folder" /><span>{w.name}</span><span className="muted">{w.document_count}</span></button>)}</div><button className="text-button" onClick={() => { setSwitcher(false); setCreating(true); }}><Icon name="plus" size={15} />New workspace</button></div></Dialog>}
    {panel === 'documents' && workspace && <DocumentPanel workspace={workspace} close={() => setPanel(null)} jobs={jobMap[workspace.id] || []} trackJob={trackJob} removeWorkspace={() => setRemove({ kind: 'workspace', id: workspace.id, name: workspace.name })} />}
    {panel === 'settings' && <SettingsPanel workspaceId={workspaceId} close={() => setPanel(null)} trackJob={trackJob} />}
    {sourceIds && <SourcePanel ids={sourceIds} close={() => setSourceIds(null)} />}
    {remove && <Dialog title={`Remove ${remove.kind}`} close={() => setRemove(null)}><div className="dialog-body stack"><p>Remove “{remove.name}”{remove.kind === 'workspace' ? ' and its documents and chats' : ' and its messages'}?</p>{remove.kind === 'workspace' && <p className="muted small">Source files stay in their original location.</p>}<div className="actions"><button className="button secondary" onClick={() => setRemove(null)}>Cancel</button><button className="button danger-button" onClick={() => void confirmRemove()}>Remove {remove.kind}</button></div></div></Dialog>}
  </div>;
}
