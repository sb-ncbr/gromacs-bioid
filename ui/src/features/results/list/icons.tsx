/**
 * Confidence-status and molecule-kind icons (SPEC.md §4; icons/icons.json).
 *
 * Lucide provides status-high/waiting/searching/searched/not-searched/failed
 * and several kinds; the handoff's custom SVGs cover the ones with no Lucide
 * equivalent (status-medium/low/exact, kind-protein/lipid/unknown) — copied
 * verbatim, stroke="currentColor", aria-hidden by default.
 */
import { CircleCheck, Clock, LoaderCircle, CircleEllipsis, CircleMinus, CircleX, Dna, Atom, Zap, Droplet, type LucideIcon } from "lucide-react";
import type { MoleculeKind } from "../viewmodel";

export type IconKey =
  | "high"
  | "medium"
  | "low"
  | "none"
  | "exact"
  | "waiting"
  | "searching"
  | "searched"
  | "not_searched"
  | "failed";

export interface IconProps {
  size?: number;
  className?: string;
  "aria-hidden"?: boolean;
}

type Svg = React.FC<IconProps>;

function custom(paths: string, dashed = false): Svg {
  const C = ({ size = 18, className, ...rest }: IconProps) => (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden={rest["aria-hidden"] ?? true}
      focusable="false"
    >
      <circle cx="12" cy="12" r="9" strokeDasharray={dashed ? "3.2 2.6" : undefined} />
      <path d={paths} />
    </svg>
  );
  C.displayName = "CustomStatusIcon";
  return C;
}

const IconMedium = custom("M7.8 12.4c1.4-1.8 2.8-1.8 4.2 0s2.8 1.8 4.2 0");
const IconLow = custom(
  "M10 9.7a2.1 2.1 0 1 1 2.9 1.9c-.6.3-.9.7-.9 1.4 M12 16.2v.1",
  true,
);
const IconExact = custom("M8.5 10h7M8.5 14h7");

export const CONFIDENCE_ICONS: Record<IconKey, Svg | LucideIcon> = {
  high: CircleCheck,
  medium: IconMedium,
  low: IconLow,
  none: ({ size = 18, className, ...rest }: IconProps) => (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      className={className}
      aria-hidden={rest["aria-hidden"] ?? true}
      focusable="false"
    >
      <circle cx="12" cy="12" r="9" />
      <path d="m5.8 18.2 12.4-12.4" />
    </svg>
  ),
  exact: IconExact,
  waiting: Clock,
  searching: LoaderCircle,
  searched: CircleEllipsis,
  not_searched: CircleMinus,
  failed: CircleX,
};

/** Icon colour role per confidence key (SPEC.md §4 — colour only reinforces). */
export const CONFIDENCE_COLOR: Record<"high" | "medium" | "low" | "none" | "exact", string> = {
  high: "text-(--vm-high)",
  medium: "text-(--vm-medium)",
  low: "text-(--vm-low)",
  none: "text-(--vm-none)",
  exact: "text-(--vm-high)",
};

function kindHexagon(paths: string, dashed = false): Svg {
  const C = ({ size = 18, className, ...rest }: IconProps) => (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden={rest["aria-hidden"] ?? true}
      focusable="false"
    >
      {dashed ? (
        <>
          <path d="M12 3 19.8 7.5v9L12 21l-7.8-4.5v-9z" strokeDasharray="3 2.4" />
          <path d={paths} />
        </>
      ) : (
        <path d={paths} />
      )}
    </svg>
  );
  C.displayName = "CustomKindIcon";
  return C;
}

const KindProtein: Svg = ({ size = 18, className, ...rest }: IconProps) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    width={size}
    height={size}
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden={rest["aria-hidden"] ?? true}
    focusable="false"
  >
    <circle cx="5" cy="17" r="2" />
    <circle cx="9.5" cy="8" r="2" />
    <circle cx="15" cy="15" r="2" />
    <circle cx="19" cy="6" r="2" />
    <path d="m5.9 15.2 2.7-5.4M11 9.3l2.6 4.3M16 13.3l2.1-5.5" />
  </svg>
);
KindProtein.displayName = "KindProteinIcon";

const KindLipid: Svg = ({ size = 18, className, ...rest }: IconProps) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    width={size}
    height={size}
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden={rest["aria-hidden"] ?? true}
    focusable="false"
  >
    <circle cx="12" cy="5.5" r="3" />
    <path d="M10.5 8.6c-1 3 1 5.5 0 12.4" />
    <path d="M13.5 8.6c1 3-1 5.5 0 12.4" />
  </svg>
);
KindLipid.displayName = "KindLipidIcon";

const KindUnknown = kindHexagon(
  "M10 10a2.1 2.1 0 1 1 2.9 1.9c-.6.3-.9.7-.9 1.4 M12 16.2v.1",
  true,
);

export const KIND_ICONS: Record<MoleculeKind, Svg | LucideIcon> = {
  protein: KindProtein,
  nucleic: Dna,
  small_molecule: Atom,
  lipid: KindLipid,
  unknown: KindUnknown,
  ion: Zap,
  water: Droplet,
};
