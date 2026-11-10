import { useEffect, useRef, useState } from 'react';
import Message from './Message';

const SUGGESTIONS = [
  'How many days of annual leave do full-time employees get?',
  'What is the hotel limit for international trips?',
  'Can I fly business class?',
  'How do I report a phishing email?',
];

export default function Chat({ messages, onAsk, busy, onStop, hasDocuments }) {
  const [question, setQuestion] = useState('');
  const bottom = useRef(null);

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  const submit = (text) => {
    const value = (text ?? question).trim();
    if (!value || busy) return;
    onAsk(value);
    setQuestion('');
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-8">
        <div className="mx-auto max-w-3xl space-y-6">
          {messages.length === 0 ? (
            <div className="py-10 text-center sm:py-16">
              <img src="/favicon.svg" alt="" className="mx-auto h-12 w-12" />
              <h1 className="mt-4 text-2xl font-bold tracking-tight sm:text-3xl">Ask your documents anything</h1>
              <p className="mx-auto mt-2 max-w-lg text-sm text-slate-500">
                An agent searches your library, keeps only the passages that help, retries with a better query when
                nothing fits, and answers with a citation for every fact. If the answer is not there, it says so.
              </p>
              {hasDocuments && (
                <div className="mx-auto mt-8 grid max-w-2xl gap-2 sm:grid-cols-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => submit(s)}
                      className="card px-4 py-3 text-left text-sm text-slate-700 transition hover:border-violet-300 hover:bg-violet-50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            messages.map((m) => <Message key={m.id} message={m} />)
          )}
          <div ref={bottom} />
        </div>
      </div>

      <form
        className="border-t border-slate-200 bg-white px-4 py-3 sm:px-8"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <label htmlFor="question" className="sr-only">Question</label>
          <textarea
            id="question"
            rows={1}
            maxLength={1000}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={hasDocuments ? 'Ask a question about your documents…' : 'Upload a document to get started'}
            className="max-h-40 min-h-11 flex-1 resize-none rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none transition placeholder:text-slate-400 focus:border-violet-500 focus:ring-4 focus:ring-violet-100"
          />
          {busy ? (
            <button type="button" onClick={onStop} className="btn h-11 border border-slate-300 bg-white text-slate-700 hover:bg-slate-50">Stop</button>
          ) : (
            <button type="submit" className="btn-primary h-11" disabled={!question.trim()}>Ask</button>
          )}
        </div>
        <p className="mx-auto mt-1.5 max-w-3xl text-[11px] text-slate-400">Enter to send · Shift+Enter for a new line</p>
      </form>
    </div>
  );
}
