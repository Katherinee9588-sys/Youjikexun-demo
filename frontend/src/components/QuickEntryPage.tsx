import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import { generateCompanion, saveTextEntry, transcribeVoice } from "../api";
import { startVoiceCapture, type ActiveVoiceCapture } from "../voiceCapture";
import type { CompanionOutput, UserEntryCreate } from "../types";

type InputMode = "voice" | "text";
type RequestPhase = "idle" | "saving" | "replying";
type VoicePhase = "ready" | "requesting" | "recording" | "transcribing";

interface ConversationTurn {
  id: number;
  role: "user" | "assistant";
  text?: string;
  output?: CompanionOutput;
}

function today(): string {
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function messageFrom(caught: unknown): string {
  if (caught instanceof Error) return caught.message;
  return String(caught);
}

function MicrophoneIcon() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path d="M20 8a4 4 0 0 0-8 0v6.7a4 4 0 0 0 8 0V8Z" />
      <path d="M6.7 14.7a9.3 9.3 0 0 0 18.6 0M16 24v4M12 28h8" />
    </svg>
  );
}

function KeyboardIcon() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <rect x="4.5" y="8" width="23" height="16" rx="3" />
      <path d="M8.5 13h1M13 13h1M17.5 13h1M22 13h1M8.5 17h1M13 17h6M22 17h1M11 21h10" />
    </svg>
  );
}

interface QuickEntryPageProps {
  banner?: ReactNode;
  entered: boolean;
  onCreated: () => void;
  onEnter: () => void;
}

export function QuickEntryPage({ banner, entered, onCreated, onEnter }: QuickEntryPageProps) {
  const [inputMode, setInputMode] = useState<InputMode>("voice");
  const [requestPhase, setRequestPhase] = useState<RequestPhase>("idle");
  const [voicePhase, setVoicePhase] = useState<VoicePhase>("ready");
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [error, setError] = useState<string | null>(null);
  const captureRef = useRef<ActiveVoiceCapture | null>(null);
  const pointerYRef = useRef(0);
  const releaseWhenReadyRef = useRef(false);
  const cancelWhenReadyRef = useRef(false);
  const conversationEndRef = useRef<HTMLDivElement>(null);
  const voicePhaseRef = useRef<VoicePhase>("ready");
  const nextTurnRef = useRef(1);

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [requestPhase, turns]);

  function updateVoicePhase(next: VoicePhase) {
    voicePhaseRef.current = next;
    setVoicePhase(next);
  }

  function addTurn(turn: Omit<ConversationTurn, "id">) {
    const id = nextTurnRef.current;
    nextTurnRef.current += 1;
    setTurns((current) => [...current, { ...turn, id }]);
  }

  async function submitRecord(originalText: string, inputMethod: UserEntryCreate["input_method"]) {
    setError(null);
    setRequestPhase("saving");
    try {
      await saveTextEntry({
        record_date: today(),
        original_text: originalText,
        input_method: inputMethod,
      });
    } catch (caught: unknown) {
      setError(messageFrom(caught));
      setRequestPhase("idle");
      return;
    }

    addTurn({ role: "user", text: originalText });
    setDraft("");
    onCreated();
    setRequestPhase("replying");

    try {
      const response = await generateCompanion({ user_text: originalText });
      addTurn({ role: "assistant", output: response.output });
    } catch (caught: unknown) {
      setError(messageFrom(caught));
    }
    setRequestPhase("idle");
  }

  function submitText(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const originalText = draft.trim();
    if (originalText.length === 0) {
      setError("请先写下一句想记录的话。");
      return;
    }
    void submitRecord(originalText, "text");
  }

  async function finishVoiceRecording() {
    const capture = captureRef.current;
    if (capture === null) return;

    captureRef.current = null;
    updateVoicePhase("transcribing");
    try {
      const audio = await capture.stop();
      const transcript = await transcribeVoice(audio);
      updateVoicePhase("ready");
      await submitRecord(transcript, "voice");
    } catch (caught: unknown) {
      updateVoicePhase("ready");
      setError(messageFrom(caught));
    }
  }

  async function beginVoiceRecording() {
    if (requestPhase !== "idle" || voicePhaseRef.current !== "ready") return;

    setError(null);
    updateVoicePhase("requesting");
    try {
      const capture = await startVoiceCapture();
      captureRef.current = capture;
      if (cancelWhenReadyRef.current) {
        cancelWhenReadyRef.current = false;
        capture.cancel();
        captureRef.current = null;
        updateVoicePhase("ready");
        return;
      }
      if (releaseWhenReadyRef.current) {
        releaseWhenReadyRef.current = false;
        await finishVoiceRecording();
        return;
      }
      updateVoicePhase("recording");
    } catch (caught: unknown) {
      updateVoicePhase("ready");
      setError(messageFrom(caught));
    }
  }

  function cancelVoiceRecording() {
    if (voicePhaseRef.current === "requesting") {
      cancelWhenReadyRef.current = true;
      return;
    }
    const capture = captureRef.current;
    if (capture === null) return;
    capture.cancel();
    captureRef.current = null;
    updateVoicePhase("ready");
  }

  function handleVoicePointerDown(event: React.PointerEvent<HTMLButtonElement>) {
    if (requestPhase !== "idle") return;
    pointerYRef.current = event.clientY;
    event.currentTarget.setPointerCapture(event.pointerId);
    void beginVoiceRecording();
  }

  function handleVoicePointerMove(event: React.PointerEvent<HTMLButtonElement>) {
    if (voicePhaseRef.current !== "recording") return;
    if (event.clientY < pointerYRef.current - 72) {
      cancelVoiceRecording();
    }
  }

  function handleVoicePointerUp() {
    if (voicePhaseRef.current === "requesting") {
      releaseWhenReadyRef.current = true;
      return;
    }
    void finishVoiceRecording();
  }

  function handleVoicePointerCancel() {
    cancelVoiceRecording();
  }

  if (!entered) {
    return (
      <main className="quick-entry-page">
        <section className="quick-entry-panel">
          <section className="quick-entry-intro" aria-labelledby="quick-entry-title">
            <span className="quick-entry-kicker">有迹可循</span>
            <div>
              <h1 id="quick-entry-title">很多答案不会在今天出现</h1>
              <h2>但一次诚实的记录</h2>
              <h2>会让身体的规律慢慢浮现</h2>
            </div>
            <button type="button" className="quick-entry-intro-button" onClick={onEnter}>进入</button>
          </section>
        </section>
      </main>
    );
  }

  const isBusy = requestPhase !== "idle" || voicePhase === "requesting" || voicePhase === "transcribing";
  const showWelcomeCopy = turns.length === 0 && requestPhase === "idle" && voicePhase === "ready";

  return (
    <main className="quick-entry-page">
      <section className="quick-entry-panel" aria-labelledby="quick-entry-title">
        {banner}
        <header className="quick-entry-header">
          <span className="quick-entry-kicker">给身体留一条线索</span>
          <button
            type="button"
            className="quick-entry-mode-button"
            onClick={() => setInputMode(inputMode === "voice" ? "text" : "voice")}
            disabled={isBusy}
          >
            {inputMode === "voice" ? <KeyboardIcon /> : <MicrophoneIcon />}
            <span>{inputMode === "voice" ? "键盘输入" : "语音输入"}</span>
          </button>
        </header>

        {showWelcomeCopy ? (
          <div className="quick-entry-welcome">
            <div className="quick-entry-copy">
              <h1 id="quick-entry-title">今天，你想记录什么</h1>
              <p>不用先判断是哪种症状，想到哪里说到哪里。一句话，就是一句有效记录。</p>
            </div>
          </div>
        ) : null}

        {turns.length > 0 ? (
          <section className="conversation-history" aria-label="今天的对话">
            {turns.map((turn) => (
              <article className={`conversation-turn is-${turn.role}`} key={turn.id}>
                {turn.role === "user" ? <p>{turn.text}</p> : null}
                {turn.role === "assistant" && turn.output !== undefined ? (
                  <ol>
                    <li>{turn.output.empathy}</li>
                    <li>{turn.output.suggestion}</li>
                    <li>{turn.output.outlook}</li>
                  </ol>
                ) : null}
              </article>
            ))}
            {requestPhase === "saving" ? <p className="conversation-status">正在保存原始记录…</p> : null}
            {requestPhase === "replying" ? <p className="conversation-status">正在根据审核知识整理回复…</p> : null}
            <div ref={conversationEndRef} />
          </section>
        ) : null}

        {error !== null ? <p className="quick-entry-voice-status" role="alert">{error}</p> : null}

        {inputMode === "text" ? (
          <form className="quick-entry-form" onSubmit={submitText}>
            <label className="quick-entry-text-label" htmlFor="quick-entry-text">写下这一刻</label>
            <textarea
              id="quick-entry-text"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              maxLength={4000}
              placeholder="想到哪里写到哪里，一句话也可以。"
              disabled={isBusy}
            />
            <div className="quick-entry-form-footer">
              <span>{draft.length} / 4000</span>
              <button type="submit" className="quick-entry-submit" disabled={isBusy}>
                {requestPhase === "saving" ? "正在保存…" : requestPhase === "replying" ? "正在回复…" : "发送"}
              </button>
            </div>
          </form>
        ) : (
          <div className="quick-entry-voice-action">
            <button
              type="button"
              className={`quick-entry-orb${voicePhase === "recording" ? " is-recording" : ""}`}
              onPointerDown={handleVoicePointerDown}
              onPointerMove={handleVoicePointerMove}
              onPointerUp={handleVoicePointerUp}
              onPointerCancel={handleVoicePointerCancel}
              disabled={isBusy}
              aria-label="长按开始语音记录，松手发送，上滑取消"
            >
              <span className="quick-entry-orb-core"><MicrophoneIcon /></span>
              <span className="quick-entry-orb-ring" aria-hidden="true" />
            </button>
            {voicePhase === "recording" ? <p className="quick-entry-recording-note">松手发送 · 上滑取消</p> : null}
            {voicePhase === "requesting" ? <p className="quick-entry-recording-note">正在请求麦克风权限</p> : null}
            {voicePhase === "transcribing" ? <p className="quick-entry-recording-note">正在转写</p> : null}
          </div>
        )}
      </section>
    </main>
  );
}
