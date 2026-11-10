import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import type { FileWithPath } from "react-dropzone";
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
} from "@e-infra/design-system";
import { Loader2, Settings2 } from "lucide-react";
import Dropzone from "./Dropzone";
import ConfigEditor from "./ConfigEditor";
import PresetPicker from "./PresetPicker";
import {
  activePresetId,
  applyPreset,
  buildRunFormData,
  cloneConfig,
  parseConfigOptions,
  resolveConfigToPost,
  type RunConfig,
} from "./config";
import { ApiError, api, endpoints } from "../../lib/api/client";

interface RunCreateResponse {
  run_id: string;
  status?: string;
  message?: string;
  results_url?: string;
}

/** The API's message for a rejected config (422), else null. */
function rejectionDetail(err: unknown): string | null {
  if (!(err instanceof ApiError) || err.status !== 422) return null;
  try {
    const detail = (JSON.parse(err.body) as { detail?: unknown }).detail;
    return typeof detail === "string" ? detail : null;
  } catch {
    return null;
  }
}

export default function UploadForm() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [files, setFiles] = useState<FileWithPath[]>([]);
  const [runName, setRunName] = useState("");
  // Working copy of the run config (null = server defaults) and the copy
  // taken when the dialog opened, restored by Cancel.
  const [config, setConfig] = useState<RunConfig | null>(null);
  const [snapshot, setSnapshot] = useState<RunConfig | null>(null);
  const [configOpen, setConfigOpen] = useState(false);

  // The tunable fields with the server defaults, and the presets.
  const optionsQuery = useQuery({
    queryKey: ["configOptions"],
    queryFn: async () =>
      parseConfigOptions(await api.get<unknown>(endpoints.configOptions)),
    retry: 0,
  });
  const options = optionsQuery.data ?? null;
  const optionsUnavailable = optionsQuery.isError || (optionsQuery.isSuccess && !options);
  const base = options?.config ?? null;
  const presets = useMemo(() => options?.presets ?? [], [options]);
  const displayConfig = config ?? base;
  const presetId = displayConfig && base ? activePresetId(displayConfig, base, presets) : null;
  const presetTitle = presets.find((p) => p.id === presetId)?.title ?? "Custom";

  function handleFilesAdded(accepted: FileWithPath[]) {
    setFiles((prev) => {
      const names = new Set(prev.map((f) => `${f.name}-${f.size}-${f.lastModified}`));
      const fresh = accepted.filter(
        (f) => !names.has(`${f.name}-${f.size}-${f.lastModified}`),
      );
      return [...prev, ...fresh];
    });
  }

  function handleRemove(file: FileWithPath) {
    setFiles((prev) =>
      prev.filter((f) => !(f.name === file.name && f.size === file.size)),
    );
  }

  function openConfig() {
    setSnapshot(config);
    setConfigOpen(true);
  }

  function cancelConfig() {
    setConfig(snapshot);
    setConfigOpen(false);
  }

  const configToPost = resolveConfigToPost(displayConfig, base);

  const submit = useMutation({
    mutationFn: async () => {
      const form = buildRunFormData(files, runName, configToPost, presetId);
      return api.postForm<RunCreateResponse>(endpoints.runs, form);
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["myRuns"] });
      navigate(`/runs/${encodeURIComponent(res.run_id)}`);
    },
  });

  const canSubmit = files.length > 0 && !submit.isPending;

  return (
    <Card className="w-full">
      <CardHeader>
        <h2 className="text-2xl font-semibold leading-none text-text-heading">Annotation request</h2>
        <CardDescription>
          Upload a molecular dynamics simulation and we will identify the
          biomolecules present.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {/* Hero / plain-language intro */}
        <p className="text-sm text-text-muted">
          BioID reads your simulation files and reports which proteins, DNA,
          lipids, and other molecules are in your structure, with database
          matches and confidence scores. It is fully automatic — just drop your
          files and start the run.
        </p>
        <ul className="list-disc space-y-1 pl-5 text-sm text-text-muted">
          <li><strong>GROMACS</strong>: <code className="text-text">.tpr</code>, or <code className="text-text">.top</code> + its <code className="text-text">.itp</code> includes, plus <code className="text-text">.gro</code> coordinates</li>
          <li><strong>AMBER</strong>: <code className="text-text">.prmtop</code>/<code className="text-text">.parm7</code> + <code className="text-text">.rst7</code>/<code className="text-text">.inpcrd</code>/<code className="text-text">.nc</code>/<code className="text-text">.mdcrd</code> coordinates</li>
          <li><strong>CHARMM / NAMD</strong>: <code className="text-text">.psf</code> + <code className="text-text">.pdb</code>/<code className="text-text">.crd</code> coordinates (a <code className="text-text">.dcd</code> works as the starting frame)</li>
          <li><strong>LAMMPS</strong>: a single <code className="text-text">.data</code> file</li>
          <li><strong>Structures</strong>: <code className="text-text">.pdb</code> / <code className="text-text">.cif</code></li>
          <li><strong>Bundles</strong>: <code className="text-text">.zip</code> / <code className="text-text">.tar</code> / <code className="text-text">.tar.gz</code></li>
        </ul>

        <Dropzone
          files={files}
          onFilesAdded={handleFilesAdded}
          onRemove={handleRemove}
        />

        {/* Run name */}
        <div className="flex flex-col gap-1">
          <Label htmlFor="run-name" className="text-sm text-text-muted">
            Run name <span className="text-text-muted">(optional)</span>
          </Label>
          <Input
            id="run-name"
            value={runName}
            placeholder="e.g. POPC membrane replica 2"
            onChange={(e) => setRunName(e.target.value)}
          />
        </div>

        {/* Advanced configuration */}
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-2 text-sm text-text-muted">
            <Settings2 className="h-4 w-4" />
            Advanced configuration
          </span>
          <div className="flex items-center gap-3">
            {base && <span className="text-xs text-text-muted">{presetTitle}</span>}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={openConfig}
              disabled={!base}
            >
              Edit
            </Button>
          </div>
        </div>

        {/* Submit */}
        <Button
          type="button"
          size="lg"
          disabled={!canSubmit}
          onClick={() => submit.mutate()}
          className="w-full"
        >
          {submit.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Submitting…
            </>
          ) : files.length === 0 ? (
            "Add files to start"
          ) : (
            "Start annotation"
          )}
        </Button>

        {submit.isError && (
          <Alert variant="error">
            <AlertTitle>Could not start the annotation</AlertTitle>
            <AlertDescription>
              {rejectionDetail(submit.error)
                ? `The configuration was not accepted: ${rejectionDetail(submit.error)}.`
                : "Something went wrong while submitting your files. Please try again."}
            </AlertDescription>
          </Alert>
        )}

        {optionsUnavailable && (
          <Alert variant="warning">
            <AlertTitle>Advanced configuration unavailable</AlertTitle>
            <AlertDescription>
              The configuration options could not be loaded. You can still
              start the annotation; it will use the recommended settings.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>

      {/* Advanced configuration dialog */}
      <Dialog open={configOpen} onOpenChange={(open) => (open ? setConfigOpen(true) : cancelConfig())}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Advanced configuration</DialogTitle>
            <DialogDescription>
              Start from a preset, then fine-tune if you need to. Leave it on
              Balanced if you are not sure.
            </DialogDescription>
          </DialogHeader>
          {base && displayConfig && (
            <>
              <PresetPicker
                presets={presets}
                active={presetId}
                onPick={(p) => setConfig(applyPreset(base, p))}
              />
              <ConfigEditor config={displayConfig} onChange={setConfig} />
            </>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              className="sm:mr-auto"
              onClick={() => setConfig(base ? cloneConfig(base) : null)}
            >
              Reset to defaults
            </Button>
            <Button type="button" variant="outline" onClick={cancelConfig}>
              Cancel
            </Button>
            <Button type="button" onClick={() => setConfigOpen(false)}>
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
