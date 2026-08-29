import { useEffect, useRef } from "react";

import type { ExerciseType, LedgerEntry } from "../types";

interface LedgerDialogProps {
  entry: LedgerEntry | null;
  onClose: () => void;
}

function sleepLabel(entry: LedgerEntry): string {
  const sleep = entry.lifestyle.sleep;
  if (!sleep.recorded) return "未记录";
  if (sleep.raw_value === null) return "已记录文字描述";
  if (!sleep.comparable) return `${sleep.raw_value} 分 · 量表未确认`;
  return `${sleep.normalized_1_10} / 10`;
}

const EXERCISE_LABELS: Record<ExerciseType, string> = {
  aerobic: "有氧",
  strength: "力量",
  core: "核心",
  stretching: "拉伸",
  yoga: "瑜伽",
  walking: "步行",
  other: "其他运动/活动",
};

function exerciseSummary(entry: LedgerEntry): string {
  const types = entry.lifestyle.exercise_type;
  return types.length === 0 ? "未记录" : types.map((type) => EXERCISE_LABELS[type]).join("、");
}

export function LedgerDialog({ entry, onClose }: LedgerDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) return;
    if (entry !== null && !dialog.open) dialog.showModal();
    if (entry === null && dialog.open) dialog.close();
  }, [entry]);

  return (
    <dialog
      ref={dialogRef}
      className="ledger-dialog"
      onClose={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) event.currentTarget.close();
      }}
    >
      {entry === null ? null : (
        <article>
          <header>
            <div>
              <span className="section-kicker">身体账本</span>
              <h2>{entry.record_date}</h2>
              <p>{entry.source === "legacy_import" ? "历史导入记录" : "新提交记录"}</p>
            </div>
            <button type="button" className="close-button" onClick={() => dialogRef.current?.close()} aria-label="关闭详情">×</button>
          </header>

          <dl className="detail-grid">
            <div><dt>体重</dt><dd>{entry.morning_vitals.body_weight === null ? "未记录" : `${entry.morning_vitals.body_weight.toFixed(2)} kg`}</dd></div>
            <div><dt>体脂率</dt><dd>{entry.morning_vitals.body_fat_rate === null ? "未记录" : `${entry.morning_vitals.body_fat_rate.toFixed(1)}%`}</dd></div>
            <div><dt>睡眠</dt><dd>{sleepLabel(entry)}</dd></div>
            <div><dt>运动</dt><dd>{exerciseSummary(entry)}</dd></div>
            <div><dt>整理状态</dt><dd>{entry.extraction_status === "pending" ? "等待模型整理" : "确定性字段已提取"}</dd></div>
          </dl>

          {entry.lifestyle.exercise_details.length > 0 ? (
            <section className="dialog-section">
              <h3>运动明细</h3>
              <ul>
                {entry.lifestyle.exercise_details.map((detail, index) => (
                  <li key={`${detail.type}-${detail.raw_name}-${index}`}>
                    {detail.raw_name} · {EXERCISE_LABELS[detail.type]}
                    {detail.duration_minutes === null ? "" : ` · ${detail.duration_minutes} 分钟`}
                    {detail.sets === null ? "" : ` · ${detail.sets} 组`}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {entry.physical_signals.length > 0 ? (
            <section className="dialog-section">
              <h3>身体信号</h3>
              {entry.physical_signals.map((signal) => <p key={signal.symptom_desc}>{signal.symptom_desc}</p>)}
            </section>
          ) : null}

          {entry.legacy_feedback === null ? null : (
            <section className="dialog-section legacy-feedback">
              <h3>历史反馈</h3>
              <p>{entry.legacy_feedback.hot}</p>
              <ul>{entry.legacy_feedback.cold.map((line) => <li key={line}>{line}</li>)}</ul>
            </section>
          )}

          <details className="raw-entry">
            <summary>查看原始记录</summary>
            <p>{entry.original_text}</p>
          </details>
        </article>
      )}
    </dialog>
  );
}
