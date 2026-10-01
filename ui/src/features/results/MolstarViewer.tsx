import { Card, CardContent, CardHeader, CardTitle, Skeleton } from "@e-infra/design-system";
import type { RenderPathsResponse } from "./hooks";

export interface MolstarViewerProps {
  runId: string;
  segment: string;
  segments: string[];
  segmentMeta: Record<string, { type?: string | null; atom_count?: number | null; residue_count?: number | null }> | null;
  renderPaths: RenderPathsResponse | null;
}

/** Placeholder — replaced by the real Mol* single-plugin viewer in the molstar deliverable. */
const MolstarViewer: React.FC<MolstarViewerProps> = ({ segment, segments }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Structure viewer — {segment === "SYSTEM" ? "whole system" : `segment ${segment}`}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Skeleton className="h-96 w-full rounded-lg" />
        <p className="mt-2 text-xs text-text-muted">
          {segments.length} segment(s) — interactive 3D view lands in the next wave.
        </p>
      </CardContent>
    </Card>
  );
};

export default MolstarViewer;
