import { useEffect, useState, type ReactNode } from "react";

import { getDailySummaries, getTrends } from "./api";
import { DailyCards } from "./components/DailyCards";
import { QuickEntryPage } from "./components/QuickEntryPage";
import { TrendsPage } from "./components/TrendsPage";
import type { DailySummary, TrendsReport, View } from "./types";

const NAVIGATION: { id: View; label: string }[] = [
  { id: "today", label: "今日记录" },
  { id: "home", label: "首页" },
  { id: "track", label: "趋势" },
];

function todayKey(): string {
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function errorMessage(caught: unknown): string {
  if (caught instanceof Error) return caught.message;
  return String(caught);
}

function DeviceFrame({ children }: { children: ReactNode }) {
  return <div className="software-canvas"><section className="app-phone">{children}</section></div>;
}

function TabBar({ view, onNavigate }: { view: View; onNavigate: (view: View) => void }) {
  return (
    <nav className="mobile-tab-bar" aria-label="主要导航">
      {NAVIGATION.map((item) => (
        <button
          key={item.id}
          type="button"
          className={view === item.id ? "is-active" : ""}
          aria-current={view === item.id ? "page" : undefined}
          onClick={() => onNavigate(item.id)}
        >
          <span aria-hidden="true" className={`tab-icon tab-icon-${item.id}`} />
          {item.label}
        </button>
      ))}
    </nav>
  );
}

function LoadingPage() {
  return <div className="mobile-loading mobile-loading-page" aria-busy="true"><span /><span /><span /></div>;
}

function ErrorPage({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div className="mobile-empty-state">
      <span aria-hidden="true">!</span>
      <h1>数据暂时没有加载</h1>
      <p>{error}</p>
      <button type="button" onClick={onRetry}>重新请求</button>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState<View>("home");
  const [homeEntered, setHomeEntered] = useState(false);
  const [revision, setRevision] = useState(0);
  const [summaries, setSummaries] = useState<DailySummary[] | null>(null);
  const [summariesError, setSummariesError] = useState<string | null>(null);
  const [trends, setTrends] = useState<TrendsReport | null>(null);
  const [trendsError, setTrendsError] = useState<string | null>(null);

  useEffect(() => {
    const needsSummaries = view === "today" || (view === "home" && homeEntered);
    if (!needsSummaries || summaries !== null) return;
    const controller = new AbortController();
    setSummariesError(null);
    getDailySummaries(controller.signal)
      .then(setSummaries)
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setSummariesError(errorMessage(caught));
      });
    return () => controller.abort();
  }, [homeEntered, revision, summaries, view]);

  useEffect(() => {
    if (view !== "track" || trends !== null) return;
    const controller = new AbortController();
    setTrendsError(null);
    getTrends(controller.signal)
      .then(setTrends)
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setTrendsError(errorMessage(caught));
      });
    return () => controller.abort();
  }, [revision, trends, view]);

  function refreshAfterRecord() {
    setSummaries(null);
    setTrends(null);
    setRevision((value) => value + 1);
  }

  function retrySummaries() {
    setSummaries(null);
    setRevision((value) => value + 1);
  }

  function retryTrends() {
    setTrends(null);
    setRevision((value) => value + 1);
  }

  const latest = summaries?.[0];
  const isToday = latest?.record_date === todayKey();
  const feedbackText = latest?.copy_lines[0];
  const banner = isToday && feedbackText !== undefined ? (
    <button type="button" className="home-feedback-banner" onClick={() => setView("today")}>
      <span className="home-feedback-banner-kicker">今天的身体记录，已经整理好</span>
      <p>{feedbackText}</p>
      <span className="home-feedback-banner-action">查看<em aria-hidden="true">→</em></span>
    </button>
  ) : null;

  return (
    <DeviceFrame>
      <section hidden={view !== "home"}>
        <QuickEntryPage
          banner={banner}
          entered={homeEntered}
          onEnter={() => setHomeEntered(true)}
          onCreated={refreshAfterRecord}
        />
      </section>
      <main className="mobile-page" hidden={view !== "today"}>
        <header className="mobile-page-heading">
          <span>今天截止当下的总结</span>
          <h1>今日记录</h1>
          <p>只展示真实存在的最近三天记录；没有记录的日期不会补进来。</p>
        </header>
        {summariesError !== null ? <ErrorPage error={summariesError} onRetry={retrySummaries} /> : null}
        {summariesError === null && summaries === null ? <LoadingPage /> : null}
        {summaries !== null ? <DailyCards summaries={summaries} /> : null}
      </main>
      <main className="mobile-page" hidden={view !== "track"}>
        <header className="mobile-page-heading">
          <span>身体轨迹</span>
          <h1>趋势</h1>
          <p>设备采集、自己说的和本周总览，分开陈列。</p>
        </header>
        {trendsError !== null ? <ErrorPage error={trendsError} onRetry={retryTrends} /> : null}
        {trendsError === null && trends === null ? <LoadingPage /> : null}
        {trends !== null ? <TrendsPage report={trends} /> : null}
      </main>
      {homeEntered ? <TabBar view={view} onNavigate={setView} /> : null}
    </DeviceFrame>
  );
}
