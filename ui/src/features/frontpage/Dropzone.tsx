import { useDropzone, type FileWithPath } from "react-dropzone";
import { UploadCloud, X } from "lucide-react";
import { Badge, Button } from "@e-infra/design-system";
import { ACCEPT_MAP, fileExtension, truncateFileName } from "./fileTypes";

interface DropzoneProps {
  files: FileWithPath[];
  onFilesAdded: (files: FileWithPath[]) => void;
  onRemove: (file: FileWithPath) => void;
}

/**
 * Drag & drop / browse upload zone for simulation inputs.
 * Accept map ported from the legacy dropzone (tpr/gro/top/itp/pdb,
 * json/yaml/yml, zip/tar/tar.gz, ini).
 */
export default function Dropzone({ files, onFilesAdded, onRemove }: DropzoneProps) {
  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    accept: ACCEPT_MAP,
    multiple: true,
    noClick: true,
    noKeyboard: true,
    onDrop: (accepted) => {
      if (accepted.length > 0) onFilesAdded(accepted);
    },
  });

  return (
    <div className="flex flex-col gap-3">
      <div
        {...getRootProps()}
        className={`flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
          isDragActive
            ? "border-primary bg-tertiary-50"
            : "border-base-300 bg-surface-raised/40 hover:border-primary"
        }`}
      >
        <input {...getInputProps()} />
        <UploadCloud className="h-10 w-10 text-primary" />
        <p className="text-base font-medium text-text">
          {isDragActive ? "Drop files to add them" : "Drag & drop simulation files here"}
        </p>
        <p className="text-sm text-text-muted">or</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            open();
          }}
        >
          Browse files
        </Button>
        <p className="text-xs text-text-muted">
          GROMACS · AMBER · CHARMM/NAMD · LAMMPS · PDB/mmCIF — or .zip / .tar bundles
        </p>
      </div>

      {files.length > 0 && (
        <ul className="flex flex-col gap-2" aria-label="Selected files">
          {files.map((file) => (
            <li
              key={`${file.name}-${file.size}-${file.lastModified}`}
              className="flex items-center gap-3 rounded-lg border border-base-200 bg-surface-raised/60 px-3 py-2"
            >
              <span
                className="min-w-0 flex-1 truncate text-sm text-text"
                title={file.name}
              >
                {truncateFileName(file.name)}
              </span>
              <Badge variant="secondary" className="shrink-0 uppercase">
                {fileExtension(file.name) || "file"}
              </Badge>
              <button
                type="button"
                aria-label={`Remove ${file.name}`}
                onClick={() => onRemove(file)}
                className="shrink-0 rounded-md p-1 text-text-muted transition-colors hover:bg-base-100 hover:text-error-600"
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
