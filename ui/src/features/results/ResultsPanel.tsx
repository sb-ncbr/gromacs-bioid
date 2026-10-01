import React from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Badge,
  Progress,
  Tooltip,
  TooltipProvider,
  TooltipTrigger,
  TooltipContent,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Alert,
  AlertTitle,
  AlertDescription,
  Button,
} from "@e-infra/design-system";
import {
  Check,
  X,
  Info,
  ExternalLink,
  Shapes,
  Network,
  Dna,
  Layers,
  Hexagon,
  Droplet,
  Zap,
  Atom,
  type LucideIcon,
} from "lucide-react";
import {
  presentHits,
  bestConfidence,
  truncateName,
  resolveHitUrl,
  type VerifiedHit,
} from "./utils";

/** Molecule-type -> lucide icon (CONTEXT map; unknown -> Shapes). */
const TYPE_ICON: Record<string, LucideIcon> = {
  protein: Network,
  nucleic: Dna,
  lipid: Layers,
  carbohydrate: Hexagon,
  water: Droplet,
  solvent: Droplet,
  ion: Zap,
  small_molecule: Atom,
  other: Shapes,
  unknown: Shapes,
};

function iconFor(type: string | null | undefined): LucideIcon {
  return TYPE_ICON[type || ""] ?? Shapes;
}

function pct(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return "\u2014";
  return `${(Math.round(v * 10) / 10).toFixed(1)}%`;
}

export interface ResolverErrorItem {
  resolver_name: string;
  generator?: string | null;
  message: string;
}

export interface ResultsPanelProps {
  /** Segment id shown in the title, e.g. "A". */
  segment: string;
  /** Molecule metadata for the type/atom/residue chips. */
  molecule?: {
    type?: string | null;
    atom_count?: number | null;
    residue_count?: number | null;
  } | null;
  /** Verification payload for this segment (hits may be empty). */
  verification?: { hits?: VerifiedHit[] | null } | null;
  /** Identifiers payload (drives the degraded-resolver empty state). */
  identifiers?: {
    hits?: unknown[] | null;
    failed_resolvers?: ResolverErrorItem[] | null;
    attempted_resolvers?: string[] | null;
  } | null;
  /** Event out: jump to the Identifiers tab (degraded empty state). */
  onJumpToIdentifiers?: () => void;
  /** Event out: request a TSV/JSON export of the verification hits. */
  onExport?: (fmt: "tsv" | "json") => void;
}

const ResultsPanel: React.FC<ResultsPanelProps> = ({
  segment,
  molecule,
  verification,
  identifiers,
  onJumpToIdentifiers,
  onExport,
}) => {
  // fidelity-first: presentHits preserves the server's stored order (no re-sort)
  const hits = presentHits(verification?.hits);
  const failedResolvers: ResolverErrorItem[] = identifiers?.failed_resolvers || [];
  const best = bestConfidence(hits);
  const TypeIcon = iconFor(molecule?.type);

  return (
    <TooltipProvider delayDuration={150}>
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2 flex-wrap">
            <CardTitle className="text-lg">Segment: {segment}</CardTitle>
            {molecule?.type && (
              <Badge variant="outline" className="gap-1">
                <TypeIcon size={13} aria-hidden /> {molecule.type}
              </Badge>
            )}
            {molecule?.atom_count != null && (
              <Badge variant="secondary">{molecule.atom_count} atoms</Badge>
            )}
            {molecule?.residue_count != null && (
              <Badge variant="secondary">{molecule.residue_count} residues</Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {/* best-confidence bar (confidence of hits[0], no re-sort) */}
          <div>
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>Best confidence</span>
              <span className="tabular-nums">{pct(best)}</span>
            </div>
            <Progress value={best} className="h-2" />
          </div>

          {hits.length === 0 ? (
            failedResolvers.length > 0 ? (
              <Alert variant="error">
                <AlertTitle>
                  Identification could not be completed &mdash; some search services were unavailable.
                </AlertTitle>
                <AlertDescription>
                  {failedResolvers.length} search service(s) did not respond, so matches may be
                  missing.
                  {onJumpToIdentifiers && (
                    <button
                      type="button"
                      onClick={onJumpToIdentifiers}
                      className="ml-1 font-medium text-[#2E7D32] underline"
                    >
                      View details in the Identifiers tab
                    </button>
                  )}
                </AlertDescription>
              </Alert>
            ) : (
              <Alert>
                <AlertTitle>No confident identifications.</AlertTitle>
                <AlertDescription>
                  No verified matches were found for this segment.
                </AlertDescription>
              </Alert>
            )
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12" />
                  <TableHead>Name</TableHead>
                  <TableHead>Identifier</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Similarity</TableHead>
                  <TableHead className="w-36">Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {hits.map((h, i) => {
                  const url = resolveHitUrl(h);
                  const name = h.name ?? h.identifier;
                  return (
                    <TableRow key={`${h.identifier}-${i}`}>
                      <TableCell>
                        <span className="inline-flex items-center gap-1">
                          {h.is_verified ? (
                            <Check size={16} className="text-green-600" aria-label="Verified" />
                          ) : (
                            <X size={16} className="text-red-600" aria-label="Rejected" />
                          )}
                          {h.rejection_reason && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Info size={13} className="text-gray-400 cursor-help" />
                              </TooltipTrigger>
                              <TooltipContent>
                                Rejected: {h.rejection_reason}
                              </TooltipContent>
                            </Tooltip>
                          )}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="inline-block max-w-[16rem] truncate align-middle">
                              {truncateName(name)}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>{name}</TooltipContent>
                        </Tooltip>
                      </TableCell>
                      <TableCell>
                        {url ? (
                          <a
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[#2E7D32] hover:underline"
                          >
                            {h.identifier} <ExternalLink size={13} aria-hidden />
                          </a>
                        ) : (
                          <span>{h.identifier}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-gray-400">{h.ident_type}</span>
                      </TableCell>
                      <TableCell className="tabular-nums">{pct(h.similarity_score)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Progress value={h.final_confidence} className="h-1.5 flex-1" />
                          <span className="w-11 text-right text-xs tabular-nums">
                            {pct(h.final_confidence)}
                          </span>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}

          {onExport && hits.length > 0 && (
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => onExport("tsv")}>
                Export TSV
              </Button>
              <Button size="sm" variant="outline" onClick={() => onExport("json")}>
                Export JSON
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </TooltipProvider>
  );
};

export default ResultsPanel;
