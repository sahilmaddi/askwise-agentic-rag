import { useState } from 'react';

const LABELS = {
  route: 'Route',
  retrieve: 'Retrieve',
  grade: 'Grade',
  rewrite: 'Rewrite query',
  generate: 'Generate',
  cite: 'Cite',
  check: 'Check grounding',
};

/** The agent's steps, live while it works and collapsible afterwards. */
export default function AgentTrace({ steps, running }) {
  const [open, setOpen] = useState(false);
  const expanded = running || open;
  const total = steps.reduce((sum, s) => sum + s.ms, 0);

  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50/70">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={running}
        aria-expanded={expanded}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-xs font-medium text-slate-600"
      >
        <span className="flex items-center gap-2">
          {running ? (
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-violet-200 border-t-violet-600" aria-hidden="true" />
          ) : (
            <span className="text-violet-600" aria-hidden="true">◆</span>
          )}
          {running ? 'Agent is working…' : `Agent trace · ${steps.length} steps · ${(total / 1000).toFixed(2)} s`}
        </span>
        {!running && <span aria-hidden="true">{expanded ? '▴' : '▾'}</span>}
      </button>
      {expanded && (
        <ol className="space-y-1.5 border-t border-slate-200 px-3 py-2.5">
          {steps.map((step, i) => (
            <li key={`${step.name}-${i}`} className="flex gap-2 text-xs">
              <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${step.name === 'rewrite' ? 'bg-amber-500' : 'bg-violet-500'}`} aria-hidden="true" />
              <span className="w-28 shrink-0 font-semibold text-slate-700">{LABELS[step.name] ?? step.name}</span>
              <span className="min-w-0 flex-1 text-slate-600">{step.detail}</span>
              <span className="shrink-0 tabular-nums text-slate-400">{step.ms < 1 ? '<1' : Math.round(step.ms)} ms</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
