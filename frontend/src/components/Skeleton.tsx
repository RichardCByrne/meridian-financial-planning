import type { CSSProperties } from "react";

export function Skeleton({
  height = 16,
  width = "100%",
  radius = 4,
  style,
}: {
  height?: number | string;
  width?: number | string;
  radius?: number;
  style?: CSSProperties;
}) {
  return (
    <span
      aria-hidden
      style={{
        display: "block",
        width,
        height,
        borderRadius: radius,
        background:
          "linear-gradient(90deg, #e2e8f0 0%, #f1f5f9 50%, #e2e8f0 100%)",
        backgroundSize: "200% 100%",
        animation: "meridian-skeleton 1.4s ease-in-out infinite",
        ...style,
      }}
    />
  );
}

export function ChartSkeleton({ height = 360 }: { height?: number }) {
  return (
    <div style={{ height, display: "flex", flexDirection: "column", gap: 8 }}>
      <Skeleton height={20} width="35%" />
      <div style={{ flex: 1, display: "flex", alignItems: "flex-end", gap: 6 }}>
        {[0.4, 0.7, 0.5, 0.8, 0.6, 0.9, 0.55, 0.75, 0.65, 0.85].map((h, i) => (
          <Skeleton key={i} height={`${h * 100}%`} width="9%" radius={4} />
        ))}
      </div>
    </div>
  );
}

export function TableSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} height={32} />
      ))}
    </div>
  );
}
