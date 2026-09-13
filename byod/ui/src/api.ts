export interface Workspace { id: number; name: string; document_count: number }
export interface Chat { id: number; title: string; updated_at: string }
export interface Citation { chunk_id: number; rank: number; filename: string; locator: string }
export interface Message { id: number; role: 'user' | 'assistant'; content: string; citations: Citation[] }
export interface Document {
  id: number; filename: string; doc_type: string; unit_count: number | null;
  chunk_count: number; status: 'pending' | 'indexed' | 'failed' | 'missing'; error: string | null;
}
export interface Provider { name: string; available: boolean; configured: boolean; models: string[] }
export interface Settings {
  providers: Provider[]; active: { provider: string | null; model: string };
  embed_model: string; embed_version: string; stale_index: boolean;
  data_dir: string; retrieval_min_score: number;
}
export interface Job {
  state: string; total: number; completed: number; failed: number; skipped: number;
  current_file: string | null; errors: { filename: string; code: string; message: string }[];
  download: { file: string; completed: number; total: number } | null;
}
export interface Source { text: string; locator: string; filename: string; document_id: number }

export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method, headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === 'string' ? error.detail : 'Operation failed. Retry.');
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}

export async function streamChat(
  chat: number, content: string, documentIds: number[] | undefined, signal: AbortSignal,
  onToken: (token: string) => void, onContext: (citations: Citation[]) => void,
): Promise<void> {
  const response = await fetch(`/api/chats/${chat}/messages`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
    body: JSON.stringify({ content, document_ids: documentIds }),
  });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || 'Could not start the reply. Retry.');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', completed = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary: number;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const name = frame.split('\n').find(line => line.startsWith('event:'))?.slice(6).trim();
        const data = JSON.parse(frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trim()).join('\n'));
        if (name === 'token') onToken(data.text);
        if (name === 'context') onContext(data.chunks.map((c: { index: number } & Omit<Citation, 'rank'>) => ({ ...c, rank: c.index })));
        if (name === 'error') throw new Error(data.message);
        if (name === 'done') completed = true;
      }
    }
    if (!completed) throw new Error('The reply was interrupted. Retry the question.');
  } finally { reader.releaseLock(); }
}
