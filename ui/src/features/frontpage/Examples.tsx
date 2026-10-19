import React from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Skeleton,
} from "@e-infra/design-system";
import { ExternalLink, FlaskConical } from "lucide-react";
import { api, endpoints } from "../../lib/api/client";

/** One landing-page example card (API wave C, 2026-10-19). */
export interface ExampleRun {
  run_id: string;
  title: string;
  description: string | null;
  image_url: string;
  created_at: string;
}

interface ExamplesResponse {
  examples: ExampleRun[];
}

const EXAMPLE_COUNT = 3;

/**
 * Landing "Example analyses" section: three big cards driven by
 * GET /runs/examples (auto: newest successful runs with a rendered
 * render/system.png; curatable via the API-side BAT3_EXAMPLE_RUNS env).
 * Renders NOTHING (and hides skeletons) when the endpoint is empty or fails,
 * so the frontpage never breaks because of examples.
 */
const Examples: React.FC = () => {
  const q = useQuery({
    queryKey: ["run-examples", EXAMPLE_COUNT],
    queryFn: () => api.get<ExamplesResponse>(`${endpoints.runExamples}?limit=${EXAMPLE_COUNT}`),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  if (q.isLoading) {
    return (
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {Array.from({ length: EXAMPLE_COUNT }).map((_, i) => (
          <Skeleton key={i} className="h-72 w-full" />
        ))}
      </div>
    );
  }

  const examples = q.data?.examples ?? [];
  if (examples.length === 0) return null;

  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold text-text">Example analyses</h2>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
        {examples.slice(0, EXAMPLE_COUNT).map((ex) => (
          <Card key={ex.run_id} className="flex h-full flex-col overflow-hidden">
            <div className="relative h-48 w-full bg-gray-50">
              <img
                src={ex.image_url}
                alt={ex.title}
                className="h-full w-full object-contain"
                onError={(e) => {
                  // Broken/missing render: fall back to a neutral mono panel.
                  e.currentTarget.style.display = "none";
                }}
              />
              <FlaskConical className="absolute inset-0 m-auto -z-10 h-10 w-10 text-gray-300" />
            </div>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{ex.title}</CardTitle>
              {ex.description && (
                <CardDescription className="line-clamp-3">{ex.description}</CardDescription>
              )}
            </CardHeader>
            <CardContent className="mt-auto">
              <Link
                to={`/runs/${ex.run_id}`}
                className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
              >
                Open run <ExternalLink className="h-3.5 w-3.5" />
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};

export default Examples;
