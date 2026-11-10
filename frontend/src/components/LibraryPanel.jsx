import { useRef, useState } from 'react';
import { api, uploadDocuments } from '../lib/api';

const kb = (bytes) => (bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`);

export default function LibraryPanel({ documents, accepted, onChanged, onClose }) {
  const input = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);

  const upload = async (files) => {
    if (!files?.length) return;
    setBusy(true);
    setMessage(null);
    try {
      const results = await uploadDocuments(files);
      const added = results.filter((r) => !r.duplicate);
      const chunks = added.reduce((sum, r) => sum + r.chunks, 0);
      setMessage({
        tone: 'ok',
        text: added.length
          ? `Indexed ${added.length} document${added.length > 1 ? 's' : ''} into ${chunks} chunks.`
          : 'Already in your library.',
      });
      onChanged();
    } catch (error) {
      setMessage({ tone: 'error', text: error.message });
    } finally {
      setBusy(false);
      if (input.current) input.current.value = '';
    }
  };

  const remove = async (doc) => {
    try {
      await api(`/documents/${doc.id}`, { method: 'DELETE' });
      setMessage({ tone: 'ok', text: `Removed ${doc.filename}.` });
      onChanged();
    } catch (error) {
      setMessage({ tone: 'error', text: error.message });
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-5 pb-3 pt-5">
        <div>
          <h2 className="font-semibold">Library</h2>
          <p className="text-xs text-slate-500">{documents.length} document{documents.length === 1 ? '' : 's'} · answers come only from these</p>
        </div>
        {onClose && (
          <button type="button" onClick={onClose} className="btn-ghost -mr-2 px-2" aria-label="Close library">✕</button>
        )}
      </div>

      <div className="px-5">
        <button
          type="button"
          onClick={() => input.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); upload(e.dataTransfer.files); }}
          disabled={busy}
          className={`flex w-full flex-col items-center rounded-xl border-2 border-dashed px-4 py-6 text-center transition ${
            dragging ? 'border-violet-500 bg-violet-50' : 'border-slate-300 hover:border-violet-400 hover:bg-slate-50'
          }`}
        >
          <svg viewBox="0 0 24 24" className="h-7 w-7 text-violet-600" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
          </svg>
          <span className="mt-2 text-sm font-semibold">{busy ? 'Reading and indexing…' : 'Upload documents'}</span>
          <span className="mt-0.5 text-xs text-slate-500">Drop files here or click to browse</span>
        </button>
        <input
          ref={input}
          type="file"
          multiple
          accept={accepted.join(',')}
          className="sr-only"
          aria-label="Choose documents to upload"
          onChange={(e) => upload(e.target.files)}
        />
        {accepted.length > 0 && (
          <p className="mt-2 text-[11px] leading-relaxed text-slate-400">{accepted.join(' ')}</p>
        )}
        {message && (
          <p role="status" className={`mt-3 rounded-lg px-3 py-2 text-xs ${message.tone === 'error' ? 'bg-red-50 text-red-700' : 'bg-violet-50 text-violet-800'}`}>
            {message.text}
          </p>
        )}
      </div>

      <ul className="mt-4 flex-1 space-y-1 overflow-y-auto px-3 pb-5">
        {documents.map((doc) => (
          <li key={doc.id} className="group flex items-start gap-3 rounded-lg px-2 py-2 hover:bg-slate-50">
            <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-slate-100 text-[10px] font-bold uppercase text-slate-500">
              {doc.filename.split('.').pop().slice(0, 4)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium" title={doc.filename}>{doc.filename}</p>
              <p className="text-xs text-slate-500">
                {doc.chunks} chunks · {kb(doc.size_bytes)}{doc.pages > 1 ? ` · ${doc.pages} pages` : ''} · {doc.extractor}
              </p>
            </div>
            <button
              type="button"
              onClick={() => remove(doc)}
              className="rounded p-1 text-slate-400 opacity-100 hover:bg-red-50 hover:text-red-600 sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100"
              aria-label={`Remove ${doc.filename}`}
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3" />
              </svg>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
