import { useState } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
  Input,
  Label,
  Switch,
} from "@e-infra/design-system";
import {
  humanLabel,
  isPlumbing,
  validateNumberInput,
  FIELD_HELP,
  SECTION_HELP,
  normalizedWeights,
  type RunConfig,
  type WeightTriple,
} from "./config";

/** Live effective-weights hint for the verification section (v3.142 Phase 3).
 * Non-blocking: mirrors backend normalize_weights so the user sees the exact
 * ratios the run will compose with. */
function WeightSumNote({ sectionData }: { sectionData: unknown }) {
  const eff = normalizedWeights((sectionData ?? {}) as WeightTriple);
  if (!eff) return null;
  const pctOf = (w: number) => `${Math.round(w * 1000) / 10}%`;
  return (
    <p className="mt-1 text-xs text-text-muted">
      Confidence weights are normalized by their sum —
      effective {pctOf(eff[0])} resolver / {pctOf(eff[1])} similarity / {pctOf(eff[2])} annotation.
    </p>
  );
}

interface ConfigEditorProps {
  config: RunConfig | null;
  onChange: (updated: RunConfig) => void;
}

/**
 * Number field with validation mirroring the legacy rules:
 * empty / non-numeric and negative (for bounded fields) are rejected and the
 * previous valid value is retained. Shows an inline error message.
 */
function NumberField({
  fieldName,
  value,
  onValid,
  help,
}: {
  fieldName: string;
  value: number;
  onValid: (n: number) => void;
  help?: string;
}) {
  const [text, setText] = useState<string>(String(value));
  const [err, setErr] = useState<string | undefined>(undefined);

  // "Adjust state during render" pattern — sync display when the prop
  // changes externally (e.g. Fast Mode toggle). React re-renders
  // synchronously before committing the DOM.
  const [prevValue, setPrevValue] = useState(value);
  if (prevValue !== value) {
    setPrevValue(value);
    setText(String(value));
    setErr(undefined);
  }

  function handle(raw: string) {
    setText(raw);
    const r = validateNumberInput(raw, value, fieldName);
    if (r.ok) {
      setErr(undefined);
      onValid(r.value);
    } else {
      setErr(r.error);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={`cfg-${fieldName}`} className="text-sm text-text-muted">
        {humanLabel(fieldName)}
      </Label>
      <Input
        id={`cfg-${fieldName}`}
        type="number"
        value={text}
        onChange={(e) => handle(e.target.value)}
        className={err ? "border-error-500" : ""}
      />
      {help && <span className="text-xs text-text-muted">{help}</span>}
      {err && <span className="text-xs text-error-600">{err}</span>}
    </div>
  );
}

export default function ConfigEditor({ config, onChange }: ConfigEditorProps) {
  if (!config || Object.keys(config).length === 0) {
    return (
      <p className="py-4 text-sm text-text-muted">
        Failed to load configuration. Using fallback defaults.
      </p>
    );
  }

  const sections = Object.entries(config).filter(
    ([k, v]) => !k.startsWith("_") && v && typeof v === "object",
  );

  function setField(section: string, field: string, value: unknown) {
    const next: RunConfig = { ...config };
    const sec: Record<string, unknown> = { ...(next[section] ?? {}) };
    sec[field] = value;
    next[section] = sec;
    onChange(next);
  }

  return (
    <div className="flex max-h-[60vh] flex-col gap-1 overflow-y-auto pr-2">
      {sections.map(([sectionName, sectionData]) => {
        const fields = Object.entries(
          sectionData as Record<string, unknown>,
        ).filter(([k]) => !k.startsWith("_") && !isPlumbing(sectionName, k));
        if (fields.length === 0) return null;
        return (
          <Accordion key={sectionName} type="single" collapsible>
            <AccordionItem value={sectionName}>
              <AccordionTrigger className="text-sm font-semibold">
                <span className="flex flex-col items-start gap-0.5 text-left">
                  {humanLabel(sectionName)}
                  {SECTION_HELP[sectionName] && (
                    <span className="text-xs font-normal text-text-muted">{SECTION_HELP[sectionName]}</span>
                  )}
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {fields.map(([fieldName, v]) => {
                    if (typeof v === "boolean") {
                      return (
                        <Label
                          key={fieldName}
                          className="flex cursor-pointer items-center justify-between gap-3 text-sm"
                        >
                          <span className="text-text-muted">
                            {humanLabel(fieldName)}
                          </span>
                          <Switch
                            checked={v}
                            onCheckedChange={(c) =>
                              setField(sectionName, fieldName, c)
                            }
                          />
                        </Label>
                      );
                    }
                    if (typeof v === "number") {
                      return (
                        <NumberField
                          key={fieldName}
                          fieldName={fieldName}
                          value={v}
                          onValid={(n) => setField(sectionName, fieldName, n)}
                          help={FIELD_HELP[`${sectionName}.${fieldName}`]}
                        />
                      );
                    }
                    // string (or other scalar) -> text Input
                    const sv = v == null ? "" : String(v);
                    return (
                      <div key={fieldName} className="flex flex-col gap-1">
                        <Label
                          htmlFor={`cfg-${sectionName}-${fieldName}`}
                          className="text-sm text-text-muted"
                        >
                          {humanLabel(fieldName)}
                        </Label>
                        <Input
                          id={`cfg-${sectionName}-${fieldName}`}
                          value={sv}
                          onChange={(e) =>
                            setField(sectionName, fieldName, e.target.value)
                          }
                        />
                      </div>
                    );
                  })}
                </div>
                {sectionName === "verification" && (
                  <WeightSumNote sectionData={sectionData} />
                )}
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        );
      })}
    </div>
  );
}
