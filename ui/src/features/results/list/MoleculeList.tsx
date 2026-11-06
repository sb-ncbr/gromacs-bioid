/**
 * Molecule list — the selector answering "which molecule?" (SPEC.md §3.4).
 * Thin renderer over moleculeList.ts; selection is owned by the parent and
 * persisted in the URL together with group-by and filter (SPEC.md §5).
 */
import { useMemo, useRef, useState, type KeyboardEvent } from "react";
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Input,
  ScrollArea,
  cn,
} from "@e-infra/design-system";
import { Boxes, ChevronDown, ChevronRight, Search } from "lucide-react";
import { SYSTEM_SELECTION } from "../stage/SystemStage";
import type { Molecule, RunStatus } from "../viewmodel";
import {
  applyQuery,
  bucketsFor,
  counts,
  identGroups,
  kindGroups,
  loadCollapsed,
  saveCollapsed,
  COLLAPSED_STORAGE_PREFIX,
  type Bucket,
  type IdentRow,
  type RowView,
} from "./moleculeList";
import { CONFIDENCE_COLOR, CONFIDENCE_ICONS, type IconKey } from "./icons";
import { DistributionBar } from "./DistributionBar";

export type GroupBy = "kind" | "identification";

export interface MoleculeListProps {
  molecules: Molecule[];
  runStatus: RunStatus;
  selectedId: string | null;
  onSelect: (id: string) => void;
  groupBy: GroupBy;
  onGroupByChange: (g: GroupBy) => void;
  filter: Bucket | null;
  onFilterChange: (b: Bucket | null) => void;
  /** Namespace for persisted collapsed groups (usually the run id). */
  storageKey?: string;
}

function copiesText(n: number): string {
  return n > 1 ? `×${n.toLocaleString()}` : "";
}

function StatusIcon({ icon, size = 18 }: { icon: IconKey; size?: number }) {
  const C = CONFIDENCE_ICONS[icon];
  const color =
    icon === "high" || icon === "exact" || icon === "medium" || icon === "low" || icon === "none"
      ? CONFIDENCE_COLOR[icon]
      : "text-(--vm-muted)";
  return <C size={size} className={cn("shrink-0", color, icon === "searching" && "motion-safe:animate-spin")} />;
}

function Row({ row, selected, onSelect }: { row: RowView; selected: boolean; onSelect: () => void }) {
  const m = row.molecule;
  return (
    <button
      type="button"
      role="option"
      aria-selected={selected}
      aria-current={selected ? "true" : undefined}
      data-list-item
      onClick={onSelect}
      title={row.hint}
      className={cn(
        "flex w-full items-center gap-2.5 px-3 py-1.5 text-left transition-colors",
        "min-h-[50px] focus:outline-none focus-visible:ring-2 focus-visible:ring-(--vm-accent)",
        selected ? "bg-(--vm-accent-soft) shadow-[inset_3px_0_0_var(--vm-accent)]" : "hover:bg-(--vm-surface-2)",
      )}
    >
      <StatusIcon icon={row.icon} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-(--vm-fg)">
          {m.display_name}
          {m.copies > 1 && <span className="ml-1.5 text-xs font-normal text-(--vm-muted)">{copiesText(m.copies)}</span>}
        </span>
        <span className="block truncate text-xs text-(--vm-muted)">{row.line2}</span>
      </span>
      {row.score != null && (
        <span className={cn("text-sm tabular-nums", CONFIDENCE_COLOR[row.icon as keyof typeof CONFIDENCE_COLOR] ?? "text-(--vm-muted)")}>
          {row.score}
        </span>
      )}
    </button>
  );
}

function IdentGroupRow({
  group, open, selectedId, onToggle, onSelect,
}: {
  group: IdentRow;
  open: boolean;
  selectedId: string | null;
  onToggle: () => void;
  onSelect: (id: string) => void;
}) {
  const multi = group.memberIds.length > 1;
  const containsSelection = selectedId != null && group.memberIds.includes(selectedId);
  return (
    <div data-list-item={multi ? undefined : true}>
      <div
        className={cn(
          "flex w-full items-center gap-2.5 px-3 py-1.5 text-left min-h-[50px]",
          containsSelection && "bg-(--vm-accent-soft) shadow-[inset_3px_0_0_var(--vm-accent)]",
        )}
      >
        {multi ? (
          <button
            type="button"
            data-list-item
            aria-expanded={open}
            onClick={onToggle}
            className="flex flex-1 items-center gap-2.5 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-(--vm-accent) rounded-sm"
          >
            {open ? <ChevronDown size={14} aria-hidden /> : <ChevronRight size={14} aria-hidden />}
            <StatusIcon icon={group.icon} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-(--vm-fg)">
                {group.name}
                <span className="ml-1.5 text-xs font-normal text-(--vm-muted)">{group.count}×</span>
              </span>
              <span className="block truncate text-xs text-(--vm-muted)">{group.memberLabels.join(", ")}</span>
            </span>
            {group.score != null && <span className="text-sm tabular-nums text-(--vm-muted)">{group.score}</span>}
          </button>
        ) : (
          <button
            type="button"
            data-list-item
            aria-current={containsSelection ? "true" : undefined}
            onClick={() => onSelect(group.memberIds[0])}
            className="flex flex-1 items-center gap-2.5 text-left focus:outline-none"
            title={group.hint}
          >
            <StatusIcon icon={group.icon} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-(--vm-fg)">{group.name}</span>
            </span>
            {group.score != null && <span className="text-sm tabular-nums text-(--vm-muted)">{group.score}</span>}
          </button>
        )}
      </div>
      {multi && open && (
        <div className="ml-9 border-l border-(--vm-line-2)">
          {group.memberIds.map((id, i) => (
            <button
              key={id}
              type="button"
              data-list-item
              aria-current={selectedId === id ? "true" : undefined}
              onClick={() => onSelect(id)}
              className={cn(
                "block w-full px-3 py-1 text-left text-sm text-(--vm-fg-2) hover:bg-(--vm-surface-2)",
                selectedId === id && "bg-(--vm-accent-soft)",
              )}
            >
              {group.memberLabels[i]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function MoleculeList({
  molecules, runStatus, selectedId, onSelect, groupBy, onGroupByChange, filter, onFilterChange, storageKey,
}: MoleculeListProps) {
  const [query, setQuery] = useState("");
  const [prevKey, setPrevKey] = useState(storageKey);
  const [collapsed, setCollapsed] = useState<Set<string>>(() =>
    loadCollapsed(storageKey ? window.localStorage : null, storageKey ?? ""),
  );
  const [openIdents, setOpenIdents] = useState<Set<string>>(new Set());
  const listRef = useRef<HTMLDivElement>(null);

  // Reset persisted collapsed state when the run changes (render-time
  // adjustment — no setState-in-effect).
  if (prevKey !== storageKey) {
    setPrevKey(storageKey);
    setCollapsed(loadCollapsed(storageKey ? window.localStorage : null, storageKey ?? ""));
  }

  const finished = runStatus === "finished";
  const effectiveGroupBy: GroupBy = finished ? groupBy : "kind";

  const visible = useMemo(
    () => applyQuery(molecules, filter, query, runStatus),
    [molecules, filter, query, runStatus],
  );
  const forceExpand = query.trim() !== "" || filter != null;

  const groups = useMemo(() => kindGroups(visible, runStatus), [visible, runStatus]);
  const idents = useMemo(
    () => (effectiveGroupBy === "identification" ? identGroups(visible) : []),
    [effectiveGroupBy, visible],
  );
  const distribution = useMemo(() => counts(molecules, runStatus), [molecules, runStatus]);

  const isCollapsed = (key: string, def: boolean) =>
    forceExpand ? false : collapsed.has(key) ? true : collapsed.has(`!${key}`) ? false : def;

  const toggleCollapsed = (key: string, def: boolean) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      const current = isCollapsed(key, def);
      next.delete(key);
      next.delete(`!${key}`);
      next.add(current ? `!${key}` : key);
      if (storageKey) saveCollapsed(window.localStorage, storageKey, next);
      return next;
    });
  };

  const setAll = (collapseAll: boolean) => {
    setCollapsed(() => {
      const next = new Set<string>();
      for (const g of groups) {
        next.delete(g.key);
        next.delete(`!${g.key}`);
        next.add(collapseAll ? g.key : `!${g.key}`);
      }
      if (storageKey) saveCollapsed(window.localStorage, storageKey, next);
      return next;
    });
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const items = listRef.current?.querySelectorAll<HTMLElement>("[data-list-item]");
    if (!items?.length) return;
    e.preventDefault();
    const arr = [...items];
    const idx = arr.indexOf(document.activeElement as HTMLElement);
    const next = e.key === "ArrowDown" ? Math.min(idx + 1, arr.length - 1) : Math.max(idx - 1, 0);
    arr[next]?.focus();
  };

  const toggleIdent = (key: string) =>
    setOpenIdents((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const stats = `Molecules ${molecules.length}`;
  const noResults = molecules.length > 0 && visible.length === 0;

  return (
    <Card className="flex min-h-0 flex-col">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-base">{stats}</CardTitle>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-1 text-xs text-(--vm-muted)">
              {effectiveGroupBy === "kind" ? "By kind" : "By identification"}
              <ChevronDown size={14} aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Group by</DropdownMenuLabel>
            <DropdownMenuRadioGroup value={effectiveGroupBy} onValueChange={(v) => onGroupByChange(v as GroupBy)}>
              <DropdownMenuRadioItem value="kind">Kind of molecule</DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="identification" disabled={!finished}>
                Identification{!finished ? " (when results are ready)" : ""}
              </DropdownMenuRadioItem>
            </DropdownMenuRadioGroup>
            {effectiveGroupBy === "kind" && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuLabel>Groups</DropdownMenuLabel>
                <DropdownMenuItem onSelect={() => setAll(false)}>Expand all, including ions and water</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setAll(true)}>Collapse all</DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-2">
        <DistributionBar
          counts={distribution}
          order={bucketsFor(runStatus)}
          active={filter}
          runStatus={runStatus}
          onToggle={onFilterChange}
        />
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-(--vm-muted)" aria-hidden />
          <Input
            type="search"
            placeholder="Find a molecule"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="h-8 bg-(--vm-surface-2) pl-8 text-sm"
            aria-label="Find a molecule"
          />
        </div>
        <ScrollArea className="min-h-[240px] flex-1" style={{ maxHeight: "calc(100vh - 230px)" }}>
          <div ref={listRef} role="listbox" aria-label="Molecules" onKeyDown={onKeyDown} data-collapsed-prefix={COLLAPSED_STORAGE_PREFIX}>
            {molecules.length === 0 && (
              <p className="px-3 py-6 text-sm text-(--vm-muted)">
                Molecules appear here once your files have been read (step 1).
              </p>
            )}
            {noResults && (
              <div className="px-3 py-6 text-sm text-(--vm-muted)">
                {query.trim() ? <>No molecules match “{query.trim()}”.</> : "No molecules match this filter."}{" "}
                <button
                  type="button"
                  className="underline underline-offset-2"
                  onClick={() => {
                    setQuery("");
                    onFilterChange(null);
                  }}
                >
                  Show all
                </button>
              </div>
            )}
            {effectiveGroupBy === "kind" &&
              groups.map((g) => {
                const closed = isCollapsed(g.key, g.defaultCollapsed);
                return (
                  <div key={g.key}>
                    <button
                      type="button"
                      data-list-item
                      aria-expanded={!closed}
                      onClick={() => toggleCollapsed(g.key, g.defaultCollapsed)}
                      className="sticky top-0 z-10 flex w-full items-center gap-1 bg-(--vm-surface-2) px-3 py-1 text-left text-[11.5px] font-bold uppercase tracking-wider text-(--vm-muted)"
                    >
                      {closed ? <ChevronRight size={12} aria-hidden /> : <ChevronDown size={12} aria-hidden />}
                      {g.title} {g.rows.length}
                      {closed && <span className="ml-1 normal-case tracking-normal">{copiesText(g.copies)}</span>}
                    </button>
                    {!closed && g.rows.map((row) => (
                      <Row key={row.molecule.id} row={row} selected={selectedId === row.molecule.id} onSelect={() => onSelect(row.molecule.id)} />
                    ))}
                  </div>
                );
              })}
            {effectiveGroupBy === "identification" &&
              idents.map((g) => {
                const open = forceExpand || openIdents.has(g.key) || (selectedId != null && g.memberIds.includes(selectedId));
                return (
                  <IdentGroupRow
                    key={g.key}
                    group={g}
                    open={open}
                    selectedId={selectedId}
                    onToggle={() => toggleIdent(g.key)}
                    onSelect={onSelect}
                  />
                );
              })}
          </div>
        </ScrollArea>
        {molecules.length > 0 && (
          <button
            type="button"
            onClick={() => onSelect(SYSTEM_SELECTION)}
            aria-pressed={selectedId === SYSTEM_SELECTION}
            className={cn(
              "flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm",
              selectedId === SYSTEM_SELECTION
                ? "border-(--vm-accent) bg-(--vm-accent-soft) text-(--vm-fg)"
                : "border-(--vm-line) text-(--vm-fg-2) hover:bg-(--vm-surface-2)",
            )}
          >
            <span className="flex items-center gap-2 font-medium">
              <Boxes size={14} aria-hidden />
              Whole system
            </span>
            <span className="text-xs text-(--vm-muted)">
              {molecules.length.toLocaleString()} molecules ·{" "}
              {molecules.reduce((s, m) => s + m.atoms_per_copy * m.copies, 0).toLocaleString()} atoms
            </span>
          </button>
        )}
      </CardContent>
    </Card>
  );
}

export default MoleculeList;
