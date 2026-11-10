/** Small building blocks shared by the admin sections. */
import type { ComponentType, ReactNode } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
  Badge,
  Button,
  Card,
  cn,
} from "@e-infra/design-system";
import { TriangleAlert } from "lucide-react";
import type { Tone } from "./format";

const TONES: Record<Tone, string> = {
  ok: "border-transparent bg-(--vm-accent-soft) text-(--vm-accent)",
  warn: "border-(--vm-attention-line) bg-(--vm-attention-bg) text-(--vm-attention)",
  error: "border-(--vm-error-line) bg-(--vm-error-bg) text-(--vm-error)",
  info: "border-(--vm-info-line) bg-(--vm-info-bg) text-(--vm-info)",
  muted: "border-(--vm-line) bg-(--vm-surface-2) text-(--vm-muted)",
};

export function ToneBadge({ tone, className, children, title }: { tone: Tone; className?: string; children: ReactNode; title?: string }) {
  return (
    <Badge variant="outline" className={cn(TONES[tone], className)} title={title}>
      {children}
    </Badge>
  );
}

type Icon = ComponentType<{ className?: string; "aria-hidden"?: boolean }>;

/** A titled card; `id` doubles as the heading anchor. */
export function Section({
  id,
  title,
  icon: IconCmp,
  actions,
  className,
  children,
}: {
  id: string;
  title: string;
  icon?: Icon;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={`${id}-title`} className={cn("min-w-0", className)}>
      <Card className="h-full min-w-0 justify-start gap-0 py-0">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-(--vm-line-2) px-4 py-3">
          <h2 id={`${id}-title`} className="flex items-center gap-2 text-base font-semibold text-(--vm-fg)">
            {IconCmp && <IconCmp className="h-4 w-4 text-(--vm-muted)" aria-hidden />}
            {title}
          </h2>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
        <div className="min-w-0 px-4 py-3">{children}</div>
      </Card>
    </section>
  );
}

/** A section (or part) the server could not build; the rest of the page still works. */
export function SectionErrorNote({ what, error }: { what: string; error: string }) {
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-md border border-(--vm-error-line) bg-(--vm-error-bg) px-3 py-2 text-sm text-(--vm-error)"
    >
      <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p className="min-w-0 break-words">
        <span className="font-medium">{what} unavailable:</span> {error}
      </p>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-2 text-sm text-text-muted">{children}</p>;
}

/** A small label/value pair. */
export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums text-(--vm-fg)">{value}</dd>
      {hint && <dd className="text-xs text-text-muted">{hint}</dd>}
    </div>
  );
}

/** A button that asks first (AlertDialog). */
export function ConfirmButton({
  label,
  ariaLabel,
  icon: IconCmp,
  title,
  description,
  confirmLabel,
  onConfirm,
  destructive = false,
  disabled = false,
  variant = "outline",
  size = "sm",
}: {
  label: ReactNode;
  ariaLabel?: string;
  icon?: Icon;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  destructive?: boolean;
  disabled?: boolean;
  variant?: "outline" | "ghost" | "error";
  size?: "sm" | "icon-sm";
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button type="button" variant={variant} size={size} disabled={disabled} aria-label={ariaLabel} title={ariaLabel}>
          {IconCmp && <IconCmp className="h-4 w-4" aria-hidden />}
          {label}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-2 text-sm text-text-muted">{description}</div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className={destructive ? "bg-error text-white hover:bg-error/90" : undefined}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
