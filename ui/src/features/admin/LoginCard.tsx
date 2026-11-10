import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button, Card, Input, Label } from "@e-infra/design-system";
import { LockKeyhole } from "lucide-react";
import { ApiError, apiErrorMessage } from "../../lib/api/client";
import { adminApi, type AdminSession } from "../../lib/api/admin";

export function LoginCard({ message, onSignedIn }: { message: string | null; onSignedIn: (s: AdminSession) => void }) {
  const [password, setPassword] = useState("");
  const login = useMutation({
    mutationFn: (pw: string) => adminApi.login(pw),
    onSuccess: (session) => {
      setPassword("");
      onSignedIn(session);
    },
  });
  const error = login.isError
    ? apiErrorMessage(login.error, login.error instanceof ApiError ? "Could not sign in." : "Could not reach the server.")
    : message;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (password) login.mutate(password);
  };
  return (
    <div className="flex min-h-[55vh] items-center justify-center py-8">
      <Card className="w-full max-w-sm gap-0 px-6 py-6">
        <form onSubmit={submit} className="space-y-4" aria-labelledby="admin-login-title">
          <div className="flex items-center gap-2">
            <LockKeyhole className="h-5 w-5 text-(--vm-muted)" aria-hidden />
            <h1 id="admin-login-title" className="text-xl font-semibold text-(--vm-fg)">
              Admin sign-in
            </h1>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="admin-password">Password</Label>
            <Input
              id="admin-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={login.isError}
              aria-describedby={error ? "admin-login-error" : undefined}
              autoFocus
              required
            />
          </div>
          {error && (
            <p id="admin-login-error" role="alert" className="text-sm text-(--vm-error)">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={!password || login.isPending}>
            {login.isPending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
