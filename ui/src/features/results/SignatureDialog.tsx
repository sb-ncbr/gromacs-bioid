import React, { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
  Badge,
  Button,
} from "@e-infra/design-system";
import { Copy, Check, Download, FileText } from "lucide-react";
import {
  signatureName,
  signatureGroup,
  signatureExtension,
  buildDownloadBlob,
  downloadBlob,
} from "./utils";

export interface SignatureDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Raw generator id, e.g. "pdb_protein". */
  generator: string;
  /** The signature value to preview/copy/download. */
  signature: string;
  /** Segment the signature belongs to, e.g. "A". */
  segment: string;
}

const SignatureDialog: React.FC<SignatureDialogProps> = ({
  open,
  onOpenChange,
  generator,
  signature,
  segment,
}) => {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) setCopied(false);
  }, [open]);

  const human = signatureName(generator);
  const group = signatureGroup(generator);
  const ext = signatureExtension(generator);
  const safeName = `${segment}_${generator}${ext}`.replace(/[^a-zA-Z0-9._-]+/g, "_");

  const doCopy = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(signature);
      } else if (typeof document !== "undefined") {
        const ta = document.createElement("textarea");
        ta.value = signature;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable (non-secure ctx) – ignore */
    }
  };

  const doDownload = () => {
    const blob = buildDownloadBlob(signature, "text/plain");
    downloadBlob(blob, safeName);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <div className="flex items-center gap-2 flex-wrap">
            <DialogTitle className="text-lg">{human}</DialogTitle>
            <Badge variant="secondary">{group}</Badge>
          </div>
          <DialogDescription className="text-sm text-gray-500">
            {human} signature generated for segment {segment} ({generator}).
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-start gap-2">
          <FileText size={16} className="mt-2 text-gray-400 shrink-0" aria-hidden />
          <pre className="flex-1 overflow-auto max-h-72 rounded-md border border-gray-200 bg-gray-50 p-3 font-mono text-xs whitespace-pre-wrap break-all">
            {signature || "(empty)"}
          </pre>
        </div>

        <DialogFooter className="gap-2">
          <Button size="sm" variant="outline" onClick={doCopy} className="gap-1">
            {copied ? <Check size={14} className="text-green-600" /> : <Copy size={14} />}
            {copied ? "Copied" : "Copy"}
          </Button>
          <Button size="sm" onClick={doDownload} className="gap-1">
            <Download size={14} /> Download {ext}
          </Button>
          <DialogClose asChild>
            <Button size="sm" variant="ghost">Close</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SignatureDialog;
