import React, { useMemo, useState } from "react";
import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@e-infra/design-system";
import { Info } from "lucide-react";
import { cn } from "@e-infra/design-system";
import type { components } from "../../lib/api/types";
import type { SignaturesResponse } from "./hooks";

type SignatureInfo = components["schemas"]["SignatureInfo"];
import {
  signatureName,
  signatureGroup,
  type SignatureGroup,
} from "./utils";
import SignatureDialog from "./SignatureDialog";

interface SignaturesTabProps {
  segment: string;
  onSegmentChange: (segment: string) => void;
  segments: string[];
  signatures: SignaturesResponse | null;
}

const GROUP_ORDER: SignatureGroup[] = [
  "Sequence",
  "Structure",
  "Chemical",
  "Fingerprint",
  "Name",
  "Domain",
  "Basic",
  "Other",
];

function toText(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

const SignaturesTab: React.FC<SignaturesTabProps> = ({
  segment,
  onSegmentChange,
  segments,
  signatures,
}) => {
  const [active, setActive] = useState<{ generator: string; signature: string } | null>(null);

  const options = segments.length > 0 ? segments : [segment];

  const segSignatures: SignatureInfo[] = useMemo(
    () => (signatures?.signatures ?? []).filter((s) => s.segment === segment),
    [signatures, segment],
  );

  const attempted: string[] = useMemo(
    () => signatures?.attempted_generators?.[segment] ?? [],
    [signatures, segment],
  );

  const byGroup = useMemo(() => {
    const map = new Map<SignatureGroup, SignatureInfo[]>();
    for (const s of segSignatures) {
      const g = signatureGroup(s.generator);
      const list = map.get(g) ?? [];
      list.push(s);
      map.set(g, list);
    }
    return map;
  }, [segSignatures]);

  const missing: string[] = useMemo(() => {
    const have = new Set(segSignatures.map((s) => s.generator));
    return attempted.filter((g) => !have.has(g));
  }, [attempted, segSignatures]);

  const groups = GROUP_ORDER.filter((g) => byGroup.has(g));

  return (
    <TooltipProvider delayDuration={150}>
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>Signatures</CardTitle>
            <Badge variant="outline">segment {segment}</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* segment select */}
          <div className="flex flex-wrap gap-1.5" role="listbox" aria-label="Signature segment">
            {options.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onSegmentChange(s)}
                className={cn(
                  "rounded-md border px-2.5 py-1 text-xs transition-colors",
                  s === segment
                    ? "border-[#2E7D32] bg-[#2E7D32]/10 font-medium text-[#1b5e20]"
                    : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50",
                )}
              >
                {s}
              </button>
            ))}
          </div>

          {signatures === null ? (
            <Skeleton className="h-24 w-full" />
          ) : segSignatures.length === 0 && missing.length === 0 ? (
            <p className="text-sm text-text-muted">
              No signatures were generated for segment {segment}.
            </p>
          ) : (
            groups.map((g) => (
              <div key={g}>
                <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
                  {g}
                </h4>
                <div className="flex flex-wrap gap-2">
                  {(byGroup.get(g) ?? []).map((s) => (
                    <button
                      key={s.generator}
                      type="button"
                      onClick={() =>
                        setActive({ generator: s.generator, signature: toText(s.signature) })
                      }
                      className="rounded-md border border-[#2E7D32]/50 bg-white px-2.5 py-1.5 text-xs text-[#1b5e20] transition-colors hover:bg-[#2E7D32]/10"
                      title={signatureName(s.generator)}
                    >
                      {signatureName(s.generator)}
                    </button>
                  ))}
                </div>
              </div>
            ))
          )}

          {missing.length > 0 && (
            <div>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
                Attempted, not generated
              </h4>
              <div className="flex flex-wrap gap-2">
                {missing.map((g) => (
                  <Tooltip key={g}>
                    <TooltipTrigger asChild>
                      <span
                        aria-disabled="true"
                        className="inline-flex cursor-not-allowed items-center gap-1 rounded-md border border-dashed border-gray-300 bg-gray-50 px-2.5 py-1.5 text-xs text-gray-400"
                      >
                        {signatureName(g)}
                        <Info size={12} aria-hidden />
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      {signatureName(g)} was attempted for this segment but did not
                      return a signature.
                    </TooltipContent>
                  </Tooltip>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {active && (
        <SignatureDialog
          open={active !== null}
          onOpenChange={(open) => {
            if (!open) setActive(null);
          }}
          generator={active.generator}
          signature={active.signature}
          segment={segment}
        />
      )}
    </TooltipProvider>
  );
};

export default SignaturesTab;
