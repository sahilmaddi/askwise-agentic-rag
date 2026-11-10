import { useCallback, useEffect, useRef, useState } from 'react';
import Chat from './components/Chat';
import Header from './components/Header';
import LibraryPanel from './components/LibraryPanel';
import { api, askStream } from './lib/api';

let nextId = 1;

export default function App() {
  const [info, setInfo] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const controller = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [infoResponse, docs] = await Promise.all([api('/info'), api('/documents')]);
      setInfo(infoResponse);
      setDocuments(docs);
      setLoadError(null);
    } catch (error) {
      setLoadError(error.message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const update = (id, change) =>
    setMessages((list) => list.map((m) => (m.id === id ? { ...m, ...(typeof change === 'function' ? change(m) : change) } : m)));

  const ask = async (question) => {
    const questionId = nextId;
    const answerId = nextId + 1;
    nextId += 2;
    setMessages((list) => [
      ...list,
      { id: questionId, role: 'user', text: question },
      { id: answerId, role: 'assistant', text: '', steps: [], citations: [], status: 'streaming' },
    ]);
    setBusy(true);
    controller.current = new AbortController();
    try {
      await askStream(
        question,
        (event) => {
          if (event.type === 'step') update(answerId, (m) => ({ steps: [...m.steps, event.step] }));
          if (event.type === 'token') update(answerId, (m) => ({ text: m.text + event.text }));
          if (event.type === 'error') update(answerId, { error: event.detail, status: 'error' });
          if (event.type === 'done') {
            const a = event.answer;
            update(answerId, {
              text: a.answer, citations: a.citations, steps: a.steps, grounded: a.grounded,
              searchQuery: a.search_query, status: 'done',
            });
          }
        },
        controller.current.signal,
      );
      update(answerId, (m) => (m.status === 'streaming' ? { status: 'done' } : {}));
    } catch (error) {
      update(answerId, { error: error.message, status: 'error' });
    } finally {
      setBusy(false);
    }
  };

  const stop = () => {
    controller.current?.abort();
    setBusy(false);
  };

  const library = (
    <LibraryPanel documents={documents} accepted={info?.acceptedFiles ?? []} onChanged={refresh} />
  );

  return (
    <div className="flex h-dvh flex-col">
      <Header info={info} documentCount={documents.length} onToggleLibrary={() => setLibraryOpen(true)} />
      {loadError && (
        <p className="border-b border-red-200 bg-red-50 px-4 py-2 text-center text-sm text-red-700" role="alert">
          {loadError}{' '}
          <button type="button" className="font-semibold underline" onClick={refresh}>Retry</button>
        </p>
      )}
      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-80 shrink-0 border-r border-slate-200 bg-white lg:block" aria-label="Library">
          {library}
        </aside>
        {libraryOpen && (
          <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Library">
            <button type="button" className="absolute inset-0 bg-slate-900/40" onClick={() => setLibraryOpen(false)} aria-label="Close library" />
            <aside className="absolute inset-y-0 left-0 w-[min(20rem,85vw)] bg-white shadow-xl">
              <LibraryPanel documents={documents} accepted={info?.acceptedFiles ?? []} onChanged={refresh} onClose={() => setLibraryOpen(false)} />
            </aside>
          </div>
        )}
        <main className="min-w-0 flex-1">
          <Chat messages={messages} onAsk={ask} busy={busy} onStop={stop} hasDocuments={documents.length > 0} />
        </main>
      </div>
    </div>
  );
}
