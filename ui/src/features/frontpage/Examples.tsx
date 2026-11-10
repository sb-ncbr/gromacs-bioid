import React, { useState } from "react";
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
import { ArrowRight, FlaskConical } from "lucide-react";
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

/** The run's system render; a flask placeholder if it is missing. */
function ExampleImage({ src }: { src: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return <FlaskConical className="absolute inset-0 m-auto h-10 w-10 text-gray-300" aria-hidden />;
  }
  return (
    <img
      src={src}
      alt=""
      loading="lazy"
      className="h-full w-full scale-110 object-contain transition-transform duration-300 group-hover:scale-[1.16]"
      onError={() => setFailed(true)}
    />
  );
}

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
          <Link
            key={ex.run_id}
            to={`/runs/${ex.run_id}`}
            className="group rounded-xl no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            <Card className="flex h-full flex-col gap-0 overflow-hidden pt-0 transition-shadow group-hover:shadow-md">
              {/* Renders have a transparent background: a soft radial wash
                  behind them, cropped slightly (the PNG keeps a margin). */}
              <div className="relative aspect-[4/3] w-full overflow-hidden bg-[radial-gradient(ellipse_at_center,var(--color-base-100)_0%,var(--surface-raised)_100%)]">
                <ExampleImage src={ex.image_url} />
              </div>
              <CardHeader className="pt-5 pb-2">
                <CardTitle className="text-base text-text-heading">{ex.title}</CardTitle>
                {ex.description && (
                  <CardDescription className="line-clamp-3">{ex.description}</CardDescription>
                )}
              </CardHeader>
              <CardContent className="mt-auto">
                <span className="inline-flex items-center gap-1 text-sm font-medium text-primary group-hover:underline">
                  Open analysis <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                </span>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
};

export default Examples;
