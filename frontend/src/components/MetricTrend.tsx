import { useId, useMemo } from "react";

import type { LedgerEntry } from "../types";

interface MetricTrendProps {
  entries: LedgerEntry[];
}

interface Point {
  date: string;
  value: number;
  x: number;
  y: number;
}

const WIDTH = 720;
const HEIGHT = 220;
const PADDING = 18;

function dayGap(previous: string, current: string): number {
  const start = new Date(`${previous}T00:00:00`).getTime();
  const end = new Date(`${current}T00:00:00`).getTime();
  return Math.round((end - start) / 86_400_000);
}

export function MetricTrend({ entries }: MetricTrendProps) {
  const titleId = useId();
  const points = useMemo<Point[]>(() => {
    const measured = [...entries]
      .filter((entry) => entry.morning_vitals.body_weight !== null)
      .sort((left, right) => left.record_date.localeCompare(right.record_date));

    if (measured.length === 0) return [];

    const values = measured.map((entry) => entry.morning_vitals.body_weight as number);
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const valueRange = maximum === minimum ? 1 : maximum - minimum;
    const firstTime = new Date(`${measured[0].record_date}T00:00:00`).getTime();
    const lastTime = new Date(`${measured[measured.length - 1].record_date}T00:00:00`).getTime();
    const timeRange = lastTime === firstTime ? 1 : lastTime - firstTime;

    return measured.map((entry) => {
      const value = entry.morning_vitals.body_weight as number;
      const timestamp = new Date(`${entry.record_date}T00:00:00`).getTime();
      return {
        date: entry.record_date,
        value,
        x: PADDING + ((timestamp - firstTime) / timeRange) * (WIDTH - PADDING * 2),
        y: PADDING + ((maximum - value) / valueRange) * (HEIGHT - PADDING * 2),
      };
    });
  }, [entries]);

  const segments = useMemo<Point[][]>(() => {
    const result: Point[][] = [];
    for (const point of points) {
      const current = result[result.length - 1];
      if (current === undefined) {
        result.push([point]);
        continue;
      }
      const previous = current[current.length - 1];
      if (dayGap(previous.date, point.date) > 1) {
        result.push([point]);
      } else {
        current.push(point);
      }
    }
    return result;
  }, [points]);

  if (points.length === 0) {
    return <p className="empty-copy">最近记录中没有可绘制的体重数据。</p>;
  }

  return (
    <div className="metric-trend">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-labelledby={titleId}>
        <title id={titleId}>按真实日期绘制的近期体重记录，缺失日期处断开</title>
        <line className="trend-grid" x1="18" y1="55" x2="702" y2="55" />
        <line className="trend-grid" x1="18" y1="110" x2="702" y2="110" />
        <line className="trend-grid" x1="18" y1="165" x2="702" y2="165" />
        {segments.map((segment) => (
          <polyline
            key={segment[0].date}
            className="trend-line"
            points={segment.map((point) => `${point.x},${point.y}`).join(" ")}
          />
        ))}
        {points.map((point) => (
          <circle key={point.date} className="trend-point" cx={point.x} cy={point.y} r="4">
            <title>{`${point.date}，${point.value.toFixed(2)} 千克`}</title>
          </circle>
        ))}
      </svg>
      <div className="trend-caption">
        <span>{points[0].date.slice(5)}</span>
        <span>未记录日期不连线</span>
        <span>{points[points.length - 1].date.slice(5)}</span>
      </div>
    </div>
  );
}
