"use client";

import clsx from "clsx";
import { Keyboard, Mic, RotateCcw, Square } from "lucide-react";
import { useEffect, useState } from "react";
import { useSpeechRecorder } from "@/lib/speech";
import { Button } from "./ui";

/** Speak (browser STT, ja-JP) or type an answer. Calls onSubmit with the final text and input mode. */
export function Recorder({
  onSubmit,
  disabled,
  maxSeconds = 30,
  submitLabel = "Check",
}: {
  onSubmit: (text: string, mode: "speech" | "typed") => void;
  disabled?: boolean;
  maxSeconds?: number;
  submitLabel?: string;
}) {
  const rec = useSpeechRecorder(maxSeconds);
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (!rec.supported) setTyping(true);
  }, [rec.supported]);

  if (typing) {
    return (
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (typed.trim()) onSubmit(typed.trim(), "typed");
        }}
      >
        {!rec.supported && (
          <p className="text-sm text-stone-600">
            Speech recognition isn&apos;t available in this browser (try Chrome or Edge). Type what you would say instead.
          </p>
        )}
        <input
          lang="ja"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder="日本語で入力…"
          aria-label="Type your answer in Japanese"
          className="jp w-full rounded-xl border border-stone-300 px-4 py-3 text-lg focus:border-brand focus:outline-none"
          disabled={disabled}
        />
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={disabled || !typed.trim()}>
            {submitLabel}
          </Button>
          {rec.supported && (
            <Button type="button" variant="ghost" onClick={() => setTyping(false)}>
              <Mic className="h-4 w-4" aria-hidden /> Use microphone
            </Button>
          )}
        </div>
      </form>
    );
  }

  const listening = rec.state === "listening";
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        {listening ? (
          <button
            type="button"
            onClick={rec.stop}
            className="flex h-16 w-16 items-center justify-center rounded-full bg-red-600 text-white shadow-lg ring-4 ring-red-200"
            aria-label="Stop recording"
          >
            <Square className="h-6 w-6" aria-hidden />
          </button>
        ) : (
          <button
            type="button"
            onClick={rec.start}
            disabled={disabled || rec.state === "requesting" || rec.state === "processing"}
            className={clsx(
              "flex h-16 w-16 items-center justify-center rounded-full bg-brand text-white shadow-lg transition hover:bg-brand-dark disabled:opacity-50",
            )}
            aria-label="Start recording"
          >
            <Mic className="h-7 w-7" aria-hidden />
          </button>
        )}
        <div className="text-sm text-stone-600" aria-live="polite">
          {rec.state === "idle" && "Tap the microphone and speak in Japanese."}
          {rec.state === "requesting" && "Waiting for microphone permission…"}
          {listening && (
            <span className="font-semibold text-red-700">
              Listening… {rec.elapsed}s / {maxSeconds}s
            </span>
          )}
          {rec.state === "processing" && "Processing…"}
          {rec.state === "done" && "Here's what we heard. Submit it or try again."}
        </div>
      </div>

      {(rec.interim || rec.transcript) && (
        <div className="rounded-xl border border-stone-200 bg-stone-50 p-3">
          <p className="text-xs uppercase tracking-wide text-stone-500">Recognised speech</p>
          <p lang="ja" className="jp text-xl">{rec.transcript || rec.interim}</p>
        </div>
      )}
      {rec.audioUrl && (
        <audio controls src={rec.audioUrl} className="h-10 w-full max-w-sm" aria-label="Your recording" />
      )}
      {rec.error && (
        <p role="alert" className="text-sm text-red-700">
          {rec.error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {rec.state === "done" && rec.transcript && (
          <Button disabled={disabled} onClick={() => onSubmit(rec.transcript, "speech")}>
            {submitLabel}
          </Button>
        )}
        {(rec.state === "done" || rec.state === "error") && (
          <Button variant="secondary" onClick={rec.reset}>
            <RotateCcw className="h-4 w-4" aria-hidden /> Try again
          </Button>
        )}
        <Button variant="ghost" onClick={() => setTyping(true)}>
          <Keyboard className="h-4 w-4" aria-hidden /> Type instead
        </Button>
      </div>
    </div>
  );
}
