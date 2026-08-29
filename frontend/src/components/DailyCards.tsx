import type { DailySummary } from "../types";

function dateLabel(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(new Date(`${value}T00:00:00`));
}

function todayKey(): string {
  return new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

function dayDiff(from: string, to: string): number {
  return Math.round((new Date(`${to}T00:00:00`).getTime() - new Date(`${from}T00:00:00`).getTime()) / 86_400_000);
}

/** 相对真实今天的称呼：今天是卡片组的最右一张，右滑回看昨天和前天。 */
function relativeLabel(recordDate: string): string {
  const diff = dayDiff(recordDate, todayKey());
  if (diff === 0) return "今天";
  if (diff === 1) return "昨天";
  if (diff === 2) return "前天";
  return "";
}

interface DailyCardsProps {
  summaries: DailySummary[];
}

export function DailyCards({ summaries }: DailyCardsProps) {
  return (
    <div className="daily-cards" role="region" aria-label="最近三天的当日记录卡片">
      {summaries.map((summary) => (
        <article className="daily-card" key={summary.record_date}>
          <header className="daily-card-header">
            <time dateTime={summary.record_date}>{dateLabel(summary.record_date)}</time>
            {relativeLabel(summary.record_date) === "" ? null : <span className="daily-card-relative">{relativeLabel(summary.record_date)}</span>}
          </header>
          {summary.tags.length > 0 ? (
            <ul className="daily-card-tags" aria-label="今日标签">
              {summary.tags.map((tag) => <li key={tag}>{tag}</li>)}
            </ul>
          ) : null}
          {summary.copy_lines.length > 0 ? (
            <p className="daily-card-copy">
              {summary.copy_lines.map((line) => <span key={line}>{line}</span>)}
            </p>
          ) : <p className="daily-card-pending">原始记录已保存，暂未生成文字总结。</p>}
          {summary.recommend.length > 0 ? (
            <section className="daily-card-block is-recommend">
              <h3>推荐继续做</h3>
              <ul>{summary.recommend.map((line) => <li key={line}>{line}</li>)}</ul>
            </section>
          ) : null}
          {summary.avoid.length > 0 ? (
            <section className="daily-card-block is-avoid">
              <h3>不建议做</h3>
              <ul>{summary.avoid.map((line) => <li key={line}>{line}</li>)}</ul>
            </section>
          ) : null}
          <footer className="daily-card-footer">共 {summary.entry_count} 条原始记录 · 不足的信息之后随时可以补</footer>
        </article>
      ))}
    </div>
  );
}
