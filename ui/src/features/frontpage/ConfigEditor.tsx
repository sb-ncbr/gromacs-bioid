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
  fieldLabel,
  humanLabel,
  identifierGroups,
  validateNumberInput,
  FIELD_HELP,
  SECTION_HELP,
  normalizedWeights,
  type ConfigSection,
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
  config: RunConfig;
  onChange: (updated: RunConfig) => void;
}

/**
 * Number field with validation mirroring the legacy rules:
 * empty / non-numeric and negative (for bounded fields) are rejected and the
 * previous valid value is retained. Shows an inline error message.
 */
function NumberField({
  id,
  fieldName,
  label,
  value,
  onValid,
  help,
}: {
  id: string;
  fieldName: string;
  label: string;
  value: number;
  onValid: (n: number) => void;
  help?: string;
}) {
  const [text, setText] = useState<string>(String(value));
  const [err, setErr] = useState<string | undefined>(undefined);

  // "Adjust state during render" pattern — sync display when the prop
  // changes externally (e.g. a preset is picked). React re-renders
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
      <Label htmlFor={id} className="text-sm text-text-muted">
        {label}
      </Label>
      <Input
        id={id}
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

/** Databases as rows with an "Exact" and a "Similar" switch, grouped by kind. */
function IdentifiersTable({
  section,
  onToggle,
}: {
  section: ConfigSection;
  onToggle: (field: string, value: boolean) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      {identifierGroups(section).map(([group, rows]) => (
        <table key={group} className="w-full text-sm">
          <thead>
            <tr className="text-xs text-text-muted">
              <th className="pb-1 text-left font-semibold uppercase tracking-wide">{group}</th>
              <th className="w-20 pb-1 text-center font-normal">Exact</th>
              <th className="w-20 pb-1 text-center font-normal">Similar</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const label = humanLabel(row.name);
              return (
                <tr key={row.name} className="border-t border-base-200">
                  <td className="py-1.5 pr-2 text-text">{label}</td>
                  {(["exact", "similar"] as const).map((kind) => {
                    const v = row[kind];
                    const field = kind === "exact" ? row.name : `${row.name}_similarity`;
                    return (
                      <td key={kind} className="py-1.5 text-center">
                        {v !== undefined && (
                          <Switch
                            checked={v}
                            aria-label={`${label} — ${kind === "exact" ? "exact" : "similar"} matches`}
                            onCheckedChange={(c) => onToggle(field, c)}
                          />
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      ))}
    </div>
  );
}

/**
 * Editor for the per-run tunable config (GET /runs/config/options): only
 * the fields the server offers are shown, in its section order.
 */
export default function ConfigEditor({ config, onChange }: ConfigEditorProps) {
  const sections = Object.entries(config).filter(
    ([k, v]) => !k.startsWith("_") && v && typeof v === "object" && Object.keys(v).length > 0,
  );

  function setField(section: string, field: string, value: unknown) {
    onChange({ ...config, [section]: { ...(config[section] ?? {}), [field]: value } });
  }

  return (
    <Accordion type="multiple" className="flex flex-col gap-1">
      {sections.map(([sectionName, sectionData]) => (
        <AccordionItem key={sectionName} value={sectionName}>
          <AccordionTrigger className="text-sm font-semibold">
            <span className="flex flex-col items-start gap-0.5 text-left">
              {sectionName === "identifiers" ? "Databases" : humanLabel(sectionName)}
              {SECTION_HELP[sectionName] && (
                <span className="text-xs font-normal text-text-muted">{SECTION_HELP[sectionName]}</span>
              )}
            </span>
          </AccordionTrigger>
          <AccordionContent>
            {sectionName === "identifiers" ? (
              <IdentifiersTable
                section={sectionData}
                onToggle={(field, v) => setField(sectionName, field, v)}
              />
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {Object.entries(sectionData).map(([fieldName, v]) => {
                  const label = fieldLabel(sectionName, fieldName);
                  const help = FIELD_HELP[`${sectionName}.${fieldName}`];
                  if (typeof v === "boolean") {
                    return (
                      <Label
                        key={fieldName}
                        className="flex cursor-pointer items-center justify-between gap-3 text-sm"
                        title={help}
                      >
                        <span className="text-text-muted">{label}</span>
                        <Switch
                          checked={v}
                          onCheckedChange={(c) => setField(sectionName, fieldName, c)}
                        />
                      </Label>
                    );
                  }
                  if (typeof v === "number") {
                    return (
                      <NumberField
                        key={fieldName}
                        id={`cfg-${sectionName}-${fieldName}`}
                        fieldName={fieldName}
                        label={label}
                        value={v}
                        onValid={(n) => setField(sectionName, fieldName, n)}
                        help={help}
                      />
                    );
                  }
                  return null;
                })}
              </div>
            )}
            {sectionName === "verification" && <WeightSumNote sectionData={sectionData} />}
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
