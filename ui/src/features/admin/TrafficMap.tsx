/**
 * Where visitors came from: OpenStreetMap tiles, one circle per place sized
 * by visitors (area ~ count). Loaded lazily (Leaflet only enters this chunk);
 * circle markers only, so Leaflet's default marker images are never needed.
 * The map refits its bounds when the window changes, not on every refresh.
 */
import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { TrafficPlace } from "../../lib/api/admin";
import { bubbleRadius } from "./traffic";

const plural = (n: number, one: string, many: string) => `${n.toLocaleString("en")} ${n === 1 ? one : many}`;

export default function TrafficMap({ places, fitKey }: { places: TrafficPlace[]; fitKey: string }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const fitted = useRef<string | null>(null);

  useEffect(() => {
    if (!el.current) return;
    const m = L.map(el.current, {
      worldCopyJump: true,
      scrollWheelZoom: false,
      minZoom: 0,
      maxZoom: 12,
      attributionControl: false,
    }).setView([25, 10], 1);
    L.control.attribution({ prefix: false }).addTo(m);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(m);
    // Wheel zoom only once the map was clicked: scrolling the page stays scrolling.
    m.on("click", () => m.scrollWheelZoom.enable());
    m.on("mouseout", () => m.scrollWheelZoom.disable());
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      m.remove();
      map.current = null;
      layer.current = null;
      fitted.current = null;
    };
  }, []);

  useEffect(() => {
    const m = map.current;
    const g = layer.current;
    if (!m || !g) return;
    g.clearLayers();
    const max = Math.max(0, ...places.map((p) => p.visitors));
    // Largest first, so smaller circles sit on top and stay hoverable.
    for (const p of [...places].sort((a, b) => b.visitors - a.visitors)) {
      const tip = document.createElement("span");
      tip.textContent = `${p.city || "Unknown place"}, ${p.country} — ${plural(p.visitors, "visitor", "visitors")}, ${plural(
        p.pageviews,
        "page view",
        "page views",
      )}`;
      L.circleMarker([p.lat, p.lon], { radius: bubbleRadius(p.visitors, max), className: "traffic-place" })
        .bindTooltip(tip, { direction: "top", offset: [0, -4] })
        .addTo(g);
    }
    if (fitted.current === fitKey) return;
    fitted.current = fitKey;
    if (places.length === 0) m.setView([25, 10], 1);
    else if (places.length === 1) m.setView([places[0].lat, places[0].lon], 5);
    else m.fitBounds(L.latLngBounds(places.map((p) => [p.lat, p.lon] as [number, number])), { padding: [24, 24], maxZoom: 6 });
  }, [places, fitKey]);

  return (
    <div
      ref={el}
      className="isolate h-72 w-full overflow-hidden rounded-md border border-(--vm-line) sm:h-80 lg:h-[26rem]"
      role="region"
      aria-label={`Map of ${plural(places.length, "place", "places")} visitors came from; the countries table lists them.`}
    />
  );
}
