import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
} from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { IndicatorsResponse, PricesResponse } from "../api";

export interface Overlays {
  sma: boolean;
  ema: boolean;
  bollinger: boolean;
  levels: boolean;
}

// Colours for chart marks. Kept here because the chart library takes values, not classes.
export const CHART_COLORS = {
  up: "#0a7b50",
  down: "#b42318",
  volume: "#a9b4bf",
  sma: ["#1f3a8a", "#7a3ea8", "#0e7490"],
  ema: ["#b45309", "#be185d"],
  band: "#6b7785",
  rsi: "#1f3a8a",
  macd: "#1f3a8a",
  signal: "#b45309",
  support: "#0a7b50",
  resistance: "#b42318",
  grid: "#e3e8ed",
  text: "#3a4754",
};

type Point = { time: string; value: number };

function points(dates: string[], values: (number | null)[] | undefined): Point[] {
  if (!values) return [];
  const out: Point[] = [];
  values.forEach((value, i) => {
    if (value !== null) out.push({ time: dates[i], value });
  });
  return out;
}

export function PriceChart({
  prices,
  indicators,
  overlays,
}: {
  prices: PricesResponse;
  indicators: IndicatorsResponse;
  overlays: Overlays;
}) {
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = holder.current;
    if (!element || prices.bars.length === 0) return;
    const chart: IChartApi = createChart(element, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: CHART_COLORS.text,
        fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
        panes: { separatorColor: "#c9d1d9" },
      },
      grid: {
        vertLines: { color: CHART_COLORS.grid },
        horzLines: { color: CHART_COLORS.grid },
      },
      rightPriceScale: { borderColor: "#c9d1d9" },
      timeScale: { borderColor: "#c9d1d9" },
    });

    const { dates, series, parameters } = indicators;
    const line = (color: string, title: string, pane = 0, width: 1 | 2 = 1, dashed = false) =>
      chart.addSeries(
        LineSeries,
        {
          color,
          title,
          lineWidth: width,
          lineStyle: dashed ? LineStyle.Dashed : LineStyle.Solid,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        },
        pane,
      );

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: CHART_COLORS.up,
      downColor: CHART_COLORS.down,
      borderUpColor: CHART_COLORS.up,
      borderDownColor: CHART_COLORS.down,
      wickUpColor: CHART_COLORS.up,
      wickDownColor: CHART_COLORS.down,
      priceLineVisible: false,
    });
    candles.priceScale().applyOptions({ scaleMargins: { top: 0.06, bottom: 0.24 } });
    candles.setData(
      prices.bars.map((bar) => ({
        time: bar.date,
        open: bar.adj_open,
        high: bar.adj_high,
        low: bar.adj_low,
        close: bar.adj_close,
      })),
    );

    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
      color: CHART_COLORS.volume,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    volume.setData(prices.bars.map((bar) => ({ time: bar.date, value: bar.volume })));

    if (overlays.sma) {
      parameters.sma_windows.forEach((window, i) => {
        line(CHART_COLORS.sma[i % 3], `SMA ${window}`, 0, 2).setData(
          points(dates, series[`sma_${window}`]),
        );
      });
    }
    if (overlays.ema) {
      parameters.ema_windows.forEach((window, i) => {
        line(CHART_COLORS.ema[i % 2], `EMA ${window}`).setData(
          points(dates, series[`ema_${window}`]),
        );
      });
    }
    if (overlays.bollinger) {
      line(CHART_COLORS.band, "BB upper", 0, 1, true).setData(points(dates, series.bb_upper));
      line(CHART_COLORS.band, "BB lower", 0, 1, true).setData(points(dates, series.bb_lower));
    }
    if (overlays.levels) {
      indicators.support.forEach((level) =>
        candles.createPriceLine({
          price: level.price,
          color: CHART_COLORS.support,
          lineStyle: LineStyle.Dotted,
          lineWidth: 2,
          axisLabelVisible: true,
          title: "support",
        }),
      );
      indicators.resistance.forEach((level) =>
        candles.createPriceLine({
          price: level.price,
          color: CHART_COLORS.resistance,
          lineStyle: LineStyle.Dotted,
          lineWidth: 2,
          axisLabelVisible: true,
          title: "resistance",
        }),
      );
    }

    const rsi = line(CHART_COLORS.rsi, `RSI ${parameters.rsi_period}`, 1, 2);
    rsi.setData(points(dates, series.rsi));
    for (const price of [30, 70]) {
      rsi.createPriceLine({
        price,
        color: CHART_COLORS.band,
        lineStyle: LineStyle.Dashed,
        lineWidth: 1,
        axisLabelVisible: false,
        title: "",
      });
    }

    const histogram = chart.addSeries(
      HistogramSeries,
      { priceLineVisible: false, lastValueVisible: false, title: "MACD hist" },
      2,
    );
    histogram.setData(
      points(dates, series.macd_histogram).map((p) => ({
        ...p,
        color: p.value >= 0 ? "#8cc9b0" : "#e5a59f",
      })),
    );
    line(CHART_COLORS.macd, "MACD", 2, 2).setData(points(dates, series.macd));
    line(CHART_COLORS.signal, "Signal", 2).setData(points(dates, series.macd_signal));

    const panes = chart.panes();
    panes[0]?.setStretchFactor(5);
    panes[1]?.setStretchFactor(1.4);
    panes[2]?.setStretchFactor(1.6);
    chart.timeScale().setVisibleLogicalRange({
      from: Math.max(0, prices.bars.length - 160),
      to: prices.bars.length + 2,
    });

    return () => chart.remove();
  }, [prices, indicators, overlays]);

  return (
    <div
      ref={holder}
      className="chart"
      role="img"
      aria-label={`Daily candlestick chart for ${prices.symbol} with volume, RSI and MACD panels`}
    />
  );
}
