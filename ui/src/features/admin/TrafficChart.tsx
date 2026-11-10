/**
 * Visitors / page views / API requests over the window: one count axis,
 * 2px lines, a crosshair that snaps to the nearest bucket (pointer or arrow
 * keys) with one tooltip for every shown series, and a table view.
 */
import { useLayoutEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { cn } from "@e-infra/design-system";
import { bucketLabel, compactNumber, niceTicks, timeTicks, type SeriesPoint } from "./traffic";

export type SeriesKey = "visitors" | "pageviews" | "requests";

export const SERIES: { key: SeriesKey; label: string; color: string }[] = [
  { key: "visitors", label: "Visitors", color: "var(--viz-visitors)" },
  { key: "pageviews", label: "Page views", color: "var(--viz-pageviews)" },
  { key: "requests", label: "API requests", color: "var(--viz-requests)" },
];

const PLOT_H = 190;
const TOP = 10;
const AXIS_BAND = 24;
const RIGHT = 12;

function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => setWidth(Math.floor(entries[0].contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

/** A short stroke of the series colour: the identity key beside text. */
export function LineKey({ color, muted = false }: { color: string; muted?: boolean }) {
  return (
    <svg width="14" height="8" aria-hidden className="shrink-0">
      <line x1="1" y1="4" x2="13" y2="4" stroke={muted ? "var(--vm-muted)" : color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function TrafficChart({
  points,
  bucket,
  shown,
  onToggle,
}: {
  points: SeriesPoint[];
  bucket: "hour" | "day";
  shown: Record<SeriesKey, boolean>;
  onToggle: (key: SeriesKey) => void;
}) {
  const [ref, width] = useWidth();
  const [hover, setHover] = useState<number | null>(null);
  const visible = SERIES.filter((s) => shown[s.key]);
  const n = points.length;
  const max = Math.max(0, ...points.flatMap((p) => visible.map((s) => p[s.key])));
  const yTicks = niceTicks(max, 4);
  const yTop = yTicks[yTicks.length - 1] || 1;
  const left = 10 + Math.max(...yTicks.map((t) => compactNumber(t).length)) * 7;
  const plotW = Math.max(1, width - left - RIGHT);
  const x = (i: number) => left + (n <= 1 ? plotW / 2 : (i * plotW) / (n - 1));
  const y = (v: number) => TOP + PLOT_H - (v / yTop) * PLOT_H;
  const xTicks = timeTicks(points, bucket, Math.floor(plotW / 78));
  const active = hover != null && hover < n ? hover : null;

  const indexAt = (clientX: number, el: Element) => {
    const px = clientX - el.getBoundingClientRect().left;
    return Math.min(n - 1, Math.max(0, n <= 1 ? 0 : Math.round(((px - left) / plotW) * (n - 1))));
  };
  const onPointer = (e: PointerEvent<SVGSVGElement>) => n > 0 && setHover(indexAt(e.clientX, e.currentTarget));
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (n === 0) return;
    const cur = active ?? n - 1;
    const next =
      e.key === "ArrowLeft" ? cur - 1 : e.key === "ArrowRight" ? cur + 1 : e.key === "Home" ? 0 : e.key === "End" ? n - 1 : null;
    if (e.key === "Escape") setHover(null);
    if (next == null) return;
    e.preventDefault();
    setHover(Math.min(n - 1, Math.max(0, next)));
  };

  const path = (key: SeriesKey) => points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join("");
  const tipLeft = active != null && x(active) > width * 0.6;
  const showDots = n <= 3;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-1 gap-y-1" role="group" aria-label="Series shown in the chart">
        {SERIES.map((s) => (
          <button
            key={s.key}
            type="button"
            aria-pressed={shown[s.key]}
            onClick={() => onToggle(s.key)}
            className={cn(
              "flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs transition-colors",
              shown[s.key]
                ? "border-(--vm-line) bg-(--vm-surface-2) text-(--vm-fg)"
                : "border-dashed border-(--vm-line) text-text-muted",
            )}
            title={shown[s.key] ? `Hide ${s.label.toLowerCase()}` : `Show ${s.label.toLowerCase()}`}
          >
            <LineKey color={s.color} muted={!shown[s.key]} />
            {s.label}
          </button>
        ))}
      </div>
      <div
        ref={ref}
        className="relative rounded-md outline-none focus-visible:ring-2 focus-visible:ring-(--border-focus)"
        tabIndex={0}
        aria-label={`Traffic per ${bucket}, ${visible.map((s) => s.label.toLowerCase()).join(", ") || "no series shown"}. Arrow keys read the values; the table below lists them.`}
        onKeyDown={onKey}
        onFocus={() => n > 0 && setHover((h) => h ?? n - 1)}
        onBlur={() => setHover(null)}
      >
        {width > 0 && (
          <svg
            width={width}
            height={TOP + PLOT_H + AXIS_BAND}
            className="block touch-pan-y select-none"
            onPointerMove={onPointer}
            onPointerDown={onPointer}
            onPointerLeave={() => setHover(null)}
            aria-hidden
          >
            {yTicks.map((t) => (
              <g key={t}>
                <line
                  x1={left}
                  x2={width - RIGHT}
                  y1={y(t)}
                  y2={y(t)}
                  stroke={t === 0 ? "var(--vm-muted)" : "var(--viz-grid)"}
                  strokeOpacity={t === 0 ? 0.6 : 1}
                  strokeWidth={1}
                  shapeRendering="crispEdges"
                />
                <text x={left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize="11" fill="var(--viz-axis)" className="tabular-nums">
                  {compactNumber(t)}
                </text>
              </g>
            ))}
            {xTicks.map((t) => (
              <text
                key={t.index}
                x={x(t.index)}
                y={TOP + PLOT_H + 16}
                textAnchor={x(t.index) < left + 20 ? "start" : x(t.index) > width - RIGHT - 20 ? "end" : "middle"}
                fontSize="11"
                fill="var(--viz-axis)"
                className="tabular-nums"
              >
                {t.label}
              </text>
            ))}
            {active != null && (
              <line
                x1={x(active)}
                x2={x(active)}
                y1={TOP}
                y2={TOP + PLOT_H}
                stroke="var(--vm-muted)"
                strokeOpacity={0.7}
                strokeWidth={1}
                shapeRendering="crispEdges"
              />
            )}
            {n > 1 &&
              visible.map((s) => (
                <path key={s.key} d={path(s.key)} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
              ))}
            {visible.flatMap((s) =>
              points.map((p, i) =>
                showDots || i === active ? (
                  <circle key={`${s.key}-${i}`} cx={x(i)} cy={y(p[s.key])} r={4} fill={s.color} stroke="var(--viz-surface)" strokeWidth={2} />
                ) : null,
              ),
            )}
          </svg>
        )}
        {active != null && visible.length > 0 && (
          <div
            className="pointer-events-none absolute z-10 min-w-36 rounded-md border border-(--vm-line) bg-background px-2.5 py-2 text-xs shadow-md"
            style={{
              top: TOP,
              left: tipLeft ? undefined : x(active) + 12,
              right: tipLeft ? width - x(active) + 12 : undefined,
            }}
          >
            <p className="mb-1 whitespace-nowrap text-text-muted">{bucketLabel(points[active].t, bucket)}</p>
            <ul className="space-y-0.5">
              {visible.map((s) => (
                <li key={s.key} className="flex items-center gap-2 whitespace-nowrap">
                  <LineKey color={s.color} />
                  <span className="font-semibold tabular-nums text-(--vm-fg)">{points[active][s.key].toLocaleString("en")}</span>
                  <span className="text-text-muted">{s.label.toLowerCase()}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

/** The chart's numbers: buckets with any traffic, newest first. */
export function SeriesTable({ points, bucket }: { points: SeriesPoint[]; bucket: "hour" | "day" }) {
  const rows = points.filter((p) => p.visitors || p.pageviews || p.requests).reverse();
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-xs text-text-muted hover:text-(--vm-fg)">
        Show the numbers ({rows.length} {bucket === "hour" ? "hour" : "day"}
        {rows.length === 1 ? "" : "s"} with traffic)
      </summary>
      <div className="mt-2 max-h-64 overflow-auto rounded-md border border-(--vm-line)">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-(--vm-surface-2) text-text-muted">
            <tr>
              <th className="px-2 py-1 text-left font-medium">{bucket === "hour" ? "Hour" : "Day (UTC)"}</th>
              {SERIES.map((s) => (
                <th key={s.key} className="px-2 py-1 text-right font-medium">
                  {s.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-(--vm-line-2)">
            {rows.map((p) => (
              <tr key={p.t}>
                <td className="px-2 py-1 whitespace-nowrap">{bucketLabel(p.t, bucket)}</td>
                {SERIES.map((s) => (
                  <td key={s.key} className="px-2 py-1 text-right tabular-nums">
                    {p[s.key].toLocaleString("en")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
