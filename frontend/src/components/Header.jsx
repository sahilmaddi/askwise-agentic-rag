const PILLS = [
  ['llm', 'Model'],
  ['embeddings', 'Embeddings'],
  ['vectorStore', 'Vector store'],
];

export default function Header({ info, onToggleLibrary, documentCount }) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="flex h-14 items-center justify-between gap-3 px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="btn-ghost -ml-2 px-2 lg:hidden"
            onClick={onToggleLibrary}
            aria-label={`Open library (${documentCount} documents)`}
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M4 6h16M4 12h16M4 18h10" />
            </svg>
          </button>
          <a href="/" className="flex items-center gap-2 font-bold tracking-tight">
            <img src="/favicon.svg" alt="" className="h-7 w-7" />
            Askwise
          </a>
          <span className="hidden rounded-md bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700 sm:inline">Agentic RAG</span>
        </div>
        <div className="flex items-center gap-2">
          {info && (
            <ul className="hidden items-center gap-2 md:flex" aria-label="Pipeline configuration">
              {PILLS.map(([key, label]) => (
                <li key={key} className="rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-600">
                  <span className="text-slate-400">{label}</span> <span className="font-medium text-slate-800">{info[key]}</span>
                </li>
              ))}
            </ul>
          )}
          <a href="/api/docs" target="_blank" rel="noreferrer" className="btn-ghost text-xs">API docs</a>
        </div>
      </div>
    </header>
  );
}
