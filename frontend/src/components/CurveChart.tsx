import { ColorType, createChart, LineSeries } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { CurvePoint } from "../api";

export interface Curve {
  name: string;
  color: string;
  points: CurvePoint[];
  emphasis?: boolean;
}

/** Cumulative return over time, one line per curve. The legend is rendered by the caller. */
export function CurveChart({ curves, label }: { curves: Curve[]; label: string }) {
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = holder.current;
    if (!element) return;
    const chart = createChart(element, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#3a4754",
        fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
      },
      grid: { vertLines: { color: "#eef1f4" }, horzLines: { color: "#e3e8ed" } },
      rightPriceScale: { borderColor: "#c9d1d9" },
      timeScale: { borderColor: "#c9d1d9" },
      localization: { priceFormatter: (v: number) => `${v.toFixed(1)}%` },
    });
    for (const curve of curves) {
      if (curve.points.length === 0) continue;
      chart
        .addSeries(LineSeries, {
          color: curve.color,
          lineWidth: curve.emphasis ? 3 : 2,
          priceLineVisible: false,
          lastValueVisible: false,
        })
        .setData(curve.points.map((p) => ({ time: p.date, value: p.return_pct })));
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [curves]);

  return <div ref={holder} className="chart chart-curve" role="img" aria-label={label} />;
}
