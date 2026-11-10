import { Input, Label, cn } from "@e-infra/design-system";

/** Retention of a run's results: "" (default), "preserve" or a number of days. */
export type Retention = string;

export const DEFAULT_RETENTION_DAYS = 30;
export const MAX_RETENTION_DAYS = 365;

/** Short text for the form's summary line. */
export function retentionSummary(value: Retention): string {
  if (value === "preserve") return "kept indefinitely";
  const days = Number(value);
  return `kept ${Number.isInteger(days) && days > 0 ? days : DEFAULT_RETENTION_DAYS} days`;
}

/** Valid when "", "preserve" or a whole number of days 1–365. */
export function retentionValid(value: Retention): boolean {
  if (value === "" || value === "preserve") return true;
  const days = Number(value);
  return Number.isInteger(days) && days >= 1 && days <= MAX_RETENTION_DAYS;
}

const OPTIONS = [
  { key: "default", label: `${DEFAULT_RETENTION_DAYS} days`, hint: "default" },
  { key: "custom", label: "Custom", hint: "number of days" },
  { key: "preserve", label: "Keep indefinitely", hint: "" },
] as const;

/** How long the results are kept before they are deleted automatically. */
export default function RetentionPicker({
  value,
  onChange,
}: {
  value: Retention;
  onChange: (next: Retention) => void;
}) {
  const mode = value === "" ? "default" : value === "preserve" ? "preserve" : "custom";
  const invalid = !retentionValid(value);
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-semibold text-text-heading">Keep the results</legend>
      <p className="text-xs text-text-muted">
        Finished runs are deleted automatically after this time. Example analyses are always kept.
      </p>
      <div role="radiogroup" aria-label="Keep the results" className="flex flex-wrap items-center gap-2">
        {OPTIONS.map((o) => (
          <button
            key={o.key}
            type="button"
            role="radio"
            aria-checked={mode === o.key}
            onClick={() => onChange(o.key === "default" ? "" : o.key === "preserve" ? "preserve" : String(DEFAULT_RETENTION_DAYS * 3))}
            className={cn(
              "rounded-lg border-2 px-3 py-1.5 text-sm transition-colors",
              mode === o.key ? "border-primary bg-primary/10 text-text-heading" : "border-base-200 text-text-muted hover:border-primary-300",
            )}
          >
            {o.label}
            {o.hint && mode !== o.key && <span className="ml-1 text-xs text-text-muted">({o.hint})</span>}
          </button>
        ))}
        {mode === "custom" && (
          <Label className="flex items-center gap-2 text-sm text-text-muted">
            <Input
              type="number"
              min={1}
              max={MAX_RETENTION_DAYS}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              className={cn("w-24", invalid && "border-error-500")}
              aria-label="Days to keep the results"
            />
            days
          </Label>
        )}
      </div>
      {invalid && <span className="text-xs text-error-600">Between 1 and {MAX_RETENTION_DAYS} days.</span>}
    </fieldset>
  );
}
