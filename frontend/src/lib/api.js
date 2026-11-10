export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function failure(response) {
  const body = await response.json().catch(() => null);
  const detail = Array.isArray(body?.detail) ? body.detail.map((d) => d.msg).join(', ') : body?.detail;
  return new ApiError(detail || `Request failed (${response.status})`, response.status);
}

export async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, options);
  } catch {
    throw new ApiError('Cannot reach the Askwise API. Is the backend running?', 0);
  }
  if (!response.ok) throw await failure(response);
  return response.status === 204 ? null : response.json();
}

export function uploadDocuments(files) {
  const form = new FormData();
  [...files].forEach((file) => form.append('files', file));
  return api('/documents', { method: 'POST', body: form });
}

/**
 * Asks a question and reads the server-sent event stream: onEvent receives
 * {type: 'step'|'token'|'done'|'error', ...} as the agent works.
 */
export async function askStream(question, onEvent, signal) {
  let response;
  try {
    response = await fetch('/api/ask/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ question }),
      signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') return;
    throw new ApiError('Cannot reach the Askwise API. Is the backend running?', 0);
  }
  if (!response.ok) throw await failure(response);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary;
    while ((boundary = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = raw.split('\n').filter((line) => line.startsWith('data: ')).map((line) => line.slice(6)).join('\n');
      if (data) onEvent(JSON.parse(data));
    }
  }
}
