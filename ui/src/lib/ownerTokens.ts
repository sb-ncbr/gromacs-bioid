/**
 * Owner tokens of the runs submitted from this browser. POST /runs (and a
 * rerun) returns a secret token; deleting or cancelling the run needs it in
 * the X-Owner-Token header. Kept in localStorage per run id; when storage is
 * unavailable the run simply cannot be deleted or cancelled from here.
 */
const KEY = "bioid.ownerTokens";

function read(): Record<string, string> {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? (parsed as Record<string, string>) : {};
  } catch {
    return {};
  }
}

function write(tokens: Record<string, string>) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(tokens));
  } catch {
    // storage blocked: nothing to remember
  }
}

export function ownerToken(runId: string): string | null {
  return read()[runId] ?? null;
}

export function rememberOwnerToken(runId: string, token: string | null | undefined) {
  if (!token) return;
  write({ ...read(), [runId]: token });
}

export function forgetOwnerToken(runId: string) {
  const tokens = read();
  delete tokens[runId];
  write(tokens);
}

/** Header for an owner-only request, or undefined when this browser has no token. */
export function ownerHeaders(runId: string): Record<string, string> | undefined {
  const token = ownerToken(runId);
  return token ? { "X-Owner-Token": token } : undefined;
}
