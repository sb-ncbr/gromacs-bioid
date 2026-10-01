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
  CardTitle,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
  Switch,
} from "@e-infra/design-system";
import { Loader2, Rocket, Settings2 } from "lucide-react";
import Dropzone from "./Dropzone";
import ConfigEditor from "./ConfigEditor";
import {
  MINIMAL_DEFAULT_CONFIG,
  buildRunFormData,
  parseConfigPayload,
  resolveConfigToPost,
  type RunConfig,
} from "./config";
import { api, endpoints } from "../../lib/api/client";

interface RunCreateResponse {
  run_id: string;
  status?: string;
  message?: string;
  results_url?: string;
}

function cloneConfig(cfg: RunConfig): RunConfig {
  return JSON.parse(JSON.stringify(cfg)) as RunConfig;
}

export default function UploadForm() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [files, setFiles] = useState<FileWithPath[]>([]);
  const [runName, setRunName] = useState("");
  const [fastMode, setFastMode] = useState(false);
  const [customized, setCustomized] = useState(false);
  const [editedConfig, setEditedConfig] = useState<RunConfig | null>(null);
  const [configOpen, setConfigOpen] = useState(false);

  // Source of truth for the run config: live default, else the legacy
  // MINIMAL_DEFAULT_CONFIG fallback (used ONLY on error).
  const configQuery = useQuery({
    queryKey: ["defaultConfig"],
    queryFn: async () =>
      parseConfigPayload(await api.get<unknown>(endpoints.configDefault)),
    retry: 0,
  });
  const usedFallback =
    configQuery.isError || configQuery.data === null || configQuery.data === undefined;
  const effectiveDefault = useMemo(
    () => configQuery.data ?? MINIMAL_DEFAULT_CONFIG,
    [configQuery.data],
  );
  const displayConfig = editedConfig ?? effectiveDefault;

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

  function handleConfigChange(next: RunConfig) {
    setEditedConfig(next);
    setCustomized(true);
  }

  function openConfig() {
    // Make sure the editor has a concrete working copy on first open.
    setEditedConfig((prev) => prev ?? cloneConfig(effectiveDefault));
    setConfigOpen(true);
  }

  function toggleFast(checked: boolean) {
    setFastMode(checked);
  }

  const configToPost = resolveConfigToPost(editedConfig ?? effectiveDefault, {
    customized,
    fastMode,
  });

  const submit = useMutation({
    mutationFn: async () => {
      const form = buildRunFormData(files, runName, configToPost);
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
        <CardTitle>Annotation request</CardTitle>
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
          <li>Topology: <code className="text-text">.tpr</code>, or <code className="text-text">.top</code> + its <code className="text-text">.itp</code> includes</li>
          <li>Coordinates: <code className="text-text">.gro</code></li>
          <li>Structure: <code className="text-text">.pdb</code></li>
          <li>Bundles: <code className="text-text">.zip</code> / <code className="text-text">.tar</code> / <code className="text-text">.tar.gz</code></li>
        </ul>

        <Dropzone
          files={files}
          onFilesAdded={handleFilesAdded}
          onRemove={handleRemove}
        />

        {/* Run name */}
        <div className="flex flex-col gap-1">
          <Label htmlFor="run-name" className="text-sm text-text-muted">
            Run name <span className="text-text-muted/70">(optional)</span>
          </Label>
          <Input
            id="run-name"
            value={runName}
            placeholder="e.g. POPC membrane replica 2"
            onChange={(e) => setRunName(e.target.value)}
          />
        </div>

        {/* Fast Mode */}
        <Label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-base-200 bg-surface-raised/40 px-3 py-2">
          <span className="flex items-center gap-2 text-sm">
            <Rocket className="h-4 w-4 text-primary" />
            <span>
              <span className="font-medium text-text">Fast Mode</span>
              <span className="block text-xs text-text-muted">
                Run signatures, identifiers and verification in parallel for a
                quicker result.
              </span>
            </span>
          </span>
          <Switch checked={fastMode} onCheckedChange={toggleFast} />
        </Label>

        {/* Advanced configuration */}
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-2 text-sm text-text-muted">
            <Settings2 className="h-4 w-4" />
            Advanced configuration
          </span>
          <div className="flex items-center gap-3">
            {(customized || fastMode) && (
              <span className="text-xs text-text-muted">customized</span>
            )}
            <Button type="button" variant="outline" size="sm" onClick={openConfig}>
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
              Something went wrong while submitting your files. Please try
              again.
            </AlertDescription>
          </Alert>
        )}

        {usedFallback && (
          <Alert variant="warning">
            <AlertTitle>Using built-in defaults</AlertTitle>
            <AlertDescription>
              The current default configuration could not be loaded, so
              sensible defaults are being used.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>

      {/* Advanced configuration dialog */}
      <Dialog open={configOpen} onOpenChange={setConfigOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Advanced configuration</DialogTitle>
            <DialogDescription>
              Fine-tune how the annotation pipeline runs. Leave unchanged if you
              are not sure.
            </DialogDescription>
          </DialogHeader>
          <ConfigEditor config={displayConfig} onChange={handleConfigChange} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setConfigOpen(false)}>
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
