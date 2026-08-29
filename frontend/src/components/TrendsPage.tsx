import type { TrendsReport } from "../types";

function dateLabel(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric" }).format(new Date(`${value}T00:00:00`));
}

function changeLabel(value: number | null): string {
  if (value === null) return "暂无上周对比";
  if (value === 0) return "与上周持平";
  return value > 0 ? `较上周 +${value}%` : `较上周 ${value}%`;
}

interface TrendsPageProps {
  report: TrendsReport;
}

export function TrendsPage({ report }: TrendsPageProps) {
  const { hardware, self_reported, weekly, anchor_date } = report;

  const selfMetrics = [
    { label: "体重", value: self_reported.body_weight },
    { label: "血压", value: self_reported.blood_pressure },
    { label: "基础体温", value: self_reported.basal_body_temp },
  ];
  const hasHistoricalValue = selfMetrics.some(
    (metric) => metric.value !== null && metric.value.date !== self_reported.anchor_date,
  );

  return (
    <>
      <p className="trends-anchor">数据截至 {dateLabel(anchor_date)}</p>

      <section className="trends-module" aria-labelledby="trends-hardware-title">
        <div className="trends-module-title">
          <h2 id="trends-hardware-title">设备采集</h2>
          <small>心率 · 血氧</small>
        </div>
        {hardware === null ? (
          <p className="trends-empty">暂未检测到设备，连接后同步心率与血氧。</p>
        ) : (
          <dl className="trends-tiles">
            <div>
              <dt>心率</dt>
              <dd>{hardware.heart_rate_bpm === null ? "-" : `${Math.round(hardware.heart_rate_bpm)} 次/分`}</dd>
            </div>
            <div>
              <dt>血氧</dt>
              <dd>{hardware.spo2_percent === null ? "-" : `${hardware.spo2_percent.toFixed(0)}%`}</dd>
            </div>
          </dl>
        )}
      </section>

      <section className="trends-module" aria-labelledby="trends-self-title">
        <div className="trends-module-title">
          <h2 id="trends-self-title">自己说的</h2>
          <small>体重 · 血压 · 基础体温</small>
        </div>
        <dl className="trends-tiles">
          {selfMetrics.map((metric) => (
            <div key={metric.label}>
              <dt>{metric.label}</dt>
              <dd>{metric.value === null ? "-" : metric.value.text}</dd>
            </div>
          ))}
        </dl>
        {selfMetrics.every((metric) => metric.value === null) ? (
          <p className="trends-note">近 7 天还没有这三项数据，想到的时候补一句就好。</p>
        ) : hasHistoricalValue ? (
          <p className="trends-note">暂未获得当日数据，以上为一周内最新历史数据。</p>
        ) : null}
      </section>

      <section className="trends-module" aria-labelledby="trends-weekly-title">
        <div className="trends-module-title">
          <h2 id="trends-weekly-title">本周总览</h2>
          <small>只统计真实留下的记录</small>
        </div>
        <dl className="trends-weekly">
          <div>
            <dt>坚持记录</dt>
            <dd>{weekly.recorded_days} / 7 天</dd>
          </div>
          <div>
            <dt>潮热</dt>
            <dd>
              {weekly.hot_flash_count} 次
              <span className="trends-change">{changeLabel(weekly.hot_flash_change_percent)}</span>
            </dd>
          </div>
          <div>
            <dt>平均睡眠</dt>
            <dd>
              {weekly.average_sleep_hours === null ? "-" : `${weekly.average_sleep_hours.toFixed(1)} 小时`}
              <span className="trends-change">{changeLabel(weekly.sleep_change_percent)}</span>
            </dd>
          </div>
        </dl>
        {weekly.recorded_days === 7 ? (
          <p className="trends-fullweek">连续记录第七天，满勤一周。</p>
        ) : null}
      </section>
    </>
  );
}