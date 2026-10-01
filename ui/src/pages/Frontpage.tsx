import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@e-infra/design-system";
import { api, endpoints } from "../lib/api/client";

interface HealthResponse {
  status?: string;
}

export default function Frontpage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<HealthResponse>(endpoints.healthLegacy),
    retry: 0,
  });

  return (
    <div className="mx-auto max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>Molecular annotation</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-text-muted">
            New upload experience is being rebuilt in this redesign wave. The full upload and run
            management flow lands next.
          </p>
          <p className="text-sm text-text-muted">
            API status:{" "}
            {health.isPending ? (
              <span>checking…</span>
            ) : health.isError ? (
              <span className="text-red-600">unreachable (expected in local dev without API)</span>
            ) : (
              <span className="text-primary">ok</span>
            )}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
