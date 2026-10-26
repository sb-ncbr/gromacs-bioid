/** Public surface of the view-model module. Components import from here only. */
export type {
  ViewModel,
  Molecule,
  MoleculeKind,
  MoleculeStatus,
  MoleculeResult,
  MatchEntry,
  RejectedEntry,
  ResultState,
  MoleculeDescriptor,
  Note,
  NoteSeverity,
  RunError,
  RunStatus,
  Stage,
  StageKey,
  StageStatus,
  DownloadEntry,
  TechnicalEntry,
} from "./types";
export type { ApiBundle, AdapterOptions } from "./adapter";
export { adapt } from "./adapter";
export { steps } from "./steps";
export { DB_LABELS, KIND_GROUP_LABELS, KIND_LABELS, STAGE_LABELS } from "./labels";
export {
  baseName,
  stripSeg,
  kindOf,
  stateOf,
  evidence,
  clause,
  elapsed,
  confLabel,
  HIGH_MIN,
  MEDIUM_MIN,
} from "./derive";
