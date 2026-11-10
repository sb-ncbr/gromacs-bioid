/** The signed-in admin session and the mutation hook every action uses. */
import { createContext, useContext, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiErrorMessage } from "../../lib/api/client";
import { isUnauthorized } from "../../lib/api/admin";

export const OVERVIEW_KEY = ["admin", "overview"] as const;

interface AdminContext {
  token: string;
  /** Drops the token and shows the sign-in form (with `message`, if any). */
  signOut: (message?: string) => void;
  /** Days a deleted run stays restorable (null if the retention section failed). */
  graceDays: number | null;
}

const Ctx = createContext<AdminContext | null>(null);

export function AdminProvider({ value, children }: { value: AdminContext; children: ReactNode }) {
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAdmin(): AdminContext {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAdmin outside AdminProvider");
  return ctx;
}

/** A 401 signs out with the server's message; anything else is a toast. */
export function useHandleAdminError() {
  const { signOut } = useAdmin();
  return (err: unknown, fallback: string) => {
    if (isUnauthorized(err)) signOut(apiErrorMessage(err, "Sign in to the admin page."));
    else toast.error(apiErrorMessage(err, fallback));
  };
}

/**
 * An admin action: runs `fn` with the token, toasts the outcome and refetches
 * the overview immediately (also after a failure: the state may have moved).
 */
export function useAdminAction<A, R>(
  fn: (token: string, args: A) => Promise<R>,
  messages: { success: (res: R, args: A) => string; failure: string },
) {
  const { token } = useAdmin();
  const qc = useQueryClient();
  const handleError = useHandleAdminError();
  return useMutation({
    mutationFn: (args: A) => fn(token, args),
    onSuccess: (res, args) => toast.success(messages.success(res, args)),
    onError: (err) => handleError(err, messages.failure),
    onSettled: () => qc.invalidateQueries({ queryKey: OVERVIEW_KEY }),
  });
}
