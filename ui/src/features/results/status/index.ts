/** Public surface of the status feature (SPEC.md §3.3). */
export { StatusStrip, default as StatusStripDefault, type StatusStripProps } from "./StatusStrip";
export {
  humanDuration,
  activeStepIndex,
  leftLine,
  timingsLine,
  stepFill,
  factsLine,
  notesPill,
  sortedNotes,
  affectsNames,
  hiddenNotesFooter,
  AFFECTS_VISIBLE,
  type RunProgress,
  type NotesPill,
  type Facts,
} from "./stripModel";
