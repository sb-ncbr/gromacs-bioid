import { Scale, SlidersHorizontal, Target, Telescope, Zap, type LucideIcon } from "lucide-react";
import { cn } from "@e-infra/design-system";
import type { RunPreset } from "./config";

const ICONS: Record<string, LucideIcon> = {
  scale: Scale,
  zap: Zap,
  target: Target,
  telescope: Telescope,
};

/**
 * Preset tiles at the top of the advanced-configuration dialog. `active` is
 * the preset the current config equals; null means it was fine-tuned.
 */
export default function PresetPicker({
  presets,
  active,
  onPick,
}: {
  presets: RunPreset[];
  active: string | null;
  onPick: (preset: RunPreset) => void;
}) {
  const current = presets.find((p) => p.id === active);
  return (
    <div className="flex flex-col gap-2">
      <div role="radiogroup" aria-label="Presets" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {presets.map((p) => {
          const Icon = ICONS[p.icon] ?? SlidersHorizontal;
          const selected = p.id === active;
          return (
            <button
              key={p.id}
              type="button"
              role="radio"
              aria-checked={selected}
              title={p.details}
              onClick={() => onPick(p)}
              className={cn(
                "flex min-h-40 min-w-0 flex-col items-start gap-2 rounded-xl border-2 p-3 text-left transition-colors",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                selected
                  ? "border-primary bg-primary/10"
                  : "border-base-200 bg-surface-raised/40 hover:border-primary-300",
              )}
            >
              <span
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-lg",
                  selected ? "bg-primary text-white" : "bg-base-100 text-primary",
                )}
              >
                <Icon className="h-5 w-5" aria-hidden />
              </span>
              <span className="text-sm font-semibold text-text-heading">{p.title}</span>
              <span className="text-xs leading-snug text-text-muted">{p.description}</span>
            </button>
          );
        })}
      </div>
      <p className="text-xs text-text-muted" aria-live="polite">
        {current
          ? current.details ?? current.description
          : "Custom: fine-tuned below. Pick a preset to start over from it."}
      </p>
    </div>
  );
}
