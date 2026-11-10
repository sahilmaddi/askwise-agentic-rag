import { Fragment, useState } from 'react';
import AgentTrace from './AgentTrace';

/** Renders answer text, turning [n] markers into buttons that highlight the matching source. */
function AnswerText({ text, onCite, active }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className="whitespace-pre-wrap leading-relaxed">
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (!match) return <Fragment key={i}>{part}</Fragment>;
        const n = Number(match[1]);
        return (
          <button
            key={i}
            type="button"
            onClick={() => onCite(n)}
            className={`mx-0.5 inline-flex h-5 min-w-5 -translate-y-0.5 items-center justify-center rounded px-1 align-middle text-[11px] font-bold transition ${
              active === n ? 'bg-violet-600 text-white' : 'bg-violet-100 text-violet-700 hover:bg-violet-200'
            }`}
            aria-label={`Source ${n}`}
          >
            {n}
          </button>
        );
      })}
    </p>
  );
}

/** Chunks are raw document text: drop Markdown heading marks and blank-line runs for display. */
const readable = (text) => text.replace(/^#{1,6}\s+/gm, '').replace(/\n{3,}/g, '\n\n').trim();

function Sources({ citations, active, onSelect }) {
  if (!citations.length) return null;
  return (
    <div className="mt-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Sources</p>
      <ul className="mt-2 grid gap-2">
        {citations.map((c) => (
          <li key={c.number}>
            <button
              type="button"
              onClick={() => onSelect(c.number)}
              aria-pressed={active === c.number}
              className={`w-full rounded-lg border p-3 text-left transition ${
                active === c.number ? 'border-violet-400 bg-violet-50 ring-2 ring-violet-100' : 'border-slate-200 hover:border-slate-300'
              }`}
            >
              <span className="flex items-center gap-2 text-xs">
                <span className="flex h-5 min-w-5 items-center justify-center rounded bg-violet-600 px-1 font-bold text-white">{c.number}</span>
                <span className="truncate font-medium text-slate-700">{c.source}</span>
                {c.page && <span className="text-slate-400">page {c.page}</span>}
              </span>
              <span className={`mt-1.5 block whitespace-pre-line text-xs leading-relaxed text-slate-600 ${active === c.number ? '' : 'line-clamp-3'}`}>
                {readable(c.text)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Message({ message }) {
  const [active, setActive] = useState(null);

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-md bg-violet-700 px-4 py-2.5 text-sm text-white">{message.text}</p>
      </div>
    );
  }

  const running = message.status === 'streaming';
  const toggle = (n) => setActive((current) => (current === n ? null : n));
  return (
    <div className="flex gap-3">
      <img src="/favicon.svg" alt="" className="mt-1 h-7 w-7 shrink-0" />
      <div className="card min-w-0 flex-1 px-4 py-3 text-sm sm:px-5 sm:py-4">
        {message.error ? (
          <p className="text-red-700" role="alert">{message.error}</p>
        ) : message.text ? (
          <AnswerText text={message.text} onCite={toggle} active={active} />
        ) : (
          <p className="text-slate-400">Thinking…</p>
        )}
        {message.status === 'done' && message.grounded === false && (
          <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
            The grounding check could not confirm every statement. Check the sources before relying on this answer.
          </p>
        )}
        {message.searchQuery && message.status === 'done' && (
          <p className="mt-3 text-xs text-slate-500">Searched for “{message.searchQuery}” after the first search found nothing useful.</p>
        )}
        <Sources citations={message.citations ?? []} active={active} onSelect={toggle} />
        {message.steps?.length > 0 && <AgentTrace steps={message.steps} running={running} />}
      </div>
    </div>
  );
}
