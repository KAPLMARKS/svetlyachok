import type { FingerprintResponse, ZoneResponse } from "@/api/types";

import { type ZoneRect, zoneLayout, zoneTypeColor } from "./zoneLayout";

interface Props {
  zones: ZoneResponse[];
  points: FingerprintResponse[];
  onPointClick?: (pointId: number) => void;
}

const colorFor = (zone: ZoneResponse): string => {
  if (zone.display_color !== null) return zone.display_color;
  return zoneTypeColor[zone.type] ?? "#1e88e5";
};

const jitter = (rect: ZoneRect, idx: number): { dx: number; dy: number } => {
  // Детерминированная сетка 5×5 внутри прямоугольника (с отступом 20px).
  const cols = 5;
  const cellW = (rect.w - 40) / cols;
  const cellH = (rect.h - 40) / cols;
  const col = idx % cols;
  const row = Math.floor(idx / cols) % cols;
  return {
    dx: 20 + col * cellW + cellW / 2,
    dy: 20 + row * cellH + cellH / 2,
  };
};

export const RadiomapCanvas = ({ zones, points, onPointClick }: Props): JSX.Element => {
  // Группируем точки по zone_id для индексации внутри jitter.
  const byZone = new Map<number, FingerprintResponse[]>();
  for (const p of points) {
    if (p.zone_id === null) continue;
    const arr = byZone.get(p.zone_id) ?? [];
    arr.push(p);
    byZone.set(p.zone_id, arr);
  }

  return (
    <svg
      viewBox="0 0 1200 800"
      preserveAspectRatio="xMidYMid meet"
      style={{
        width: "100%",
        height: "auto",
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-md)",
      }}
    >
      <image href="/office-floorplan.svg" x={0} y={0} width={1200} height={800} />

      {zones.map((zone) => {
        const rect = zoneLayout[zone.id];
        if (!rect) return null;
        const color = colorFor(zone);
        return (
          <g key={zone.id}>
            <rect
              x={rect.x}
              y={rect.y}
              width={rect.w}
              height={rect.h}
              fill={color}
              fillOpacity={0.12}
              stroke={color}
              strokeWidth={2}
            />
            <text
              x={rect.x + 10}
              y={rect.y + 22}
              fontFamily="system-ui"
              fontSize={14}
              fill={color}
              fontWeight={600}
            >
              {zone.name}
            </text>
          </g>
        );
      })}

      {Array.from(byZone.entries()).flatMap(([zoneId, zonePoints]) => {
        const rect = zoneLayout[zoneId];
        if (!rect) return [];
        const zone = zones.find((z) => z.id === zoneId);
        const color = zone !== undefined ? colorFor(zone) : "#1e88e5";
        return zonePoints.map((p, idx) => {
          const { dx, dy } = jitter(rect, idx);
          return (
            <circle
              key={p.id}
              cx={rect.x + dx}
              cy={rect.y + dy}
              r={8}
              fill={color}
              stroke="#ffffff"
              strokeWidth={2}
              style={{ cursor: onPointClick ? "pointer" : "default" }}
              onClick={() => onPointClick?.(p.id)}
            >
              <title>
                {`#${p.id}\n${p.captured_at}\n` +
                  `samples=${p.sample_count}, BSSID=${Object.keys(p.rssi_vector).length}`}
              </title>
            </circle>
          );
        });
      })}
    </svg>
  );
};
