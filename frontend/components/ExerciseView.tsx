"use client";

import clsx from "clsx";
import { Lightbulb } from "lucide-react";
import { useState } from "react";
import type { Exercise } from "@/lib/types";
import { AudioButton } from "./AudioButton";
import { JapaneseText } from "./JapaneseText";
import { Recorder } from "./Recorder";
import { Button } from "./ui";

export type Submit = (answer: string, mode: "typed" | "speech" | "choice", usedHint: boolean) => void;

export function ExerciseView({
  exercise,
  onSubmit,
  busy,
  locked,
  showReading,
  showRomaji,
}: {
  exercise: Exercise;
  onSubmit: Submit;
  busy: boolean;
  locked: boolean;
  showReading: boolean;
  showRomaji: boolean;
}) {
  const [typed, setTyped] = useState("");
  const [hintIndex, setHintIndex] = useState(-1);
  const [order, setOrder] = useState<number[]>([]);
  const [showTranslation, setShowTranslation] = useState(exercise.type !== "ja_to_en");
  const usedHint = hintIndex >= 0;
  const e = exercise;
  const isChoice = e.type === "multiple_choice" || e.type === "listening_choice";
  const hideTextForListening = e.type === "listening_choice";

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold">{e.instructions}</h2>

      {e.audio_text && (
        <div className="flex items-center gap-2">
          <AudioButton key={e.id} text={e.audio_text} size="lg" autoPlay={e.type === "listening_choice" || e.type === "presentation"} label="Play audio" />
          <AudioButton text={e.audio_text} rate={0.65} size="sm" label="Play slowly" />
          <span className="text-xs text-stone-500">Normal · slow</span>
        </div>
      )}

      {e.prompt_ja && !hideTextForListening && (
        <JapaneseText ja={e.prompt_ja} reading={e.prompt_reading} romaji={e.prompt_romaji}
          en={e.type === "presentation" || showTranslation ? e.prompt_en : null}
          showReading={showReading} showRomaji={showRomaji} />
      )}
      {!e.prompt_ja && e.prompt_en && e.type !== "presentation" && <p className="text-xl font-medium">“{e.prompt_en}”</p>}
      {e.type === "ja_to_en" && !showTranslation && null}

      {isChoice && (
        <div className="grid gap-2 sm:grid-cols-2">
          {e.choices.map((c) => (
            <button key={c} disabled={busy || locked} onClick={() => onSubmit(c, "choice", usedHint)}
              className="jp rounded-xl border border-stone-200 bg-white px-4 py-3 text-left text-lg transition hover:border-brand hover:bg-brand-soft disabled:opacity-60" lang="ja">
              {c}
            </button>
          ))}
        </div>
      )}

      {e.type === "sentence_ordering" && (
        <div className="space-y-3">
          <div className="jp min-h-14 rounded-xl border-2 border-dashed border-stone-300 p-3 text-xl" lang="ja" aria-label="Your sentence">
            {order.map((idx, k) => (
              <button key={k} onClick={() => setOrder(order.filter((_, j) => j !== k))} disabled={locked}
                className="mr-2 mb-2 rounded-lg bg-brand-soft px-3 py-1 text-brand">{e.choices[idx]}</button>
            ))}
            {!order.length && <span className="text-sm text-stone-400">Tap the words below in order</span>}
          </div>
          <div className="flex flex-wrap gap-2">
            {e.choices.map((c, idx) => (
              <button key={idx} disabled={order.includes(idx) || locked} onClick={() => setOrder([...order, idx])}
                className="jp rounded-lg border border-stone-300 bg-white px-3 py-1 text-xl disabled:opacity-30" lang="ja">{c}</button>
            ))}
          </div>
          <Button disabled={order.length !== e.choices.length || busy || locked} loading={busy}
            onClick={() => onSubmit(order.map((i) => e.choices[i]).join(""), "typed", usedHint)}>Check</Button>
        </div>
      )}

      {["ja_to_en", "en_to_ja", "typed_japanese", "sentence_completion"].includes(e.type) && (
        <form className="space-y-3" onSubmit={(ev) => { ev.preventDefault(); if (typed.trim()) onSubmit(typed.trim(), "typed", usedHint); }}>
          <input value={typed} onChange={(ev) => setTyped(ev.target.value)} disabled={locked}
            lang={e.type === "ja_to_en" ? "en" : "ja"} aria-label="Your answer"
            placeholder={e.type === "ja_to_en" ? "Type in English…" : "日本語で入力…"}
            className={clsx("w-full rounded-xl border border-stone-300 px-4 py-3 text-lg focus:border-brand focus:outline-none", e.type !== "ja_to_en" && "jp")} />
          <Button type="submit" disabled={!typed.trim() || locked} loading={busy}>Check</Button>
        </form>
      )}

      {e.type === "speaking" && !locked && (
        <Recorder key={e.id} disabled={busy} onSubmit={(t, m) => onSubmit(t, m, usedHint)} />
      )}

      {e.type === "ja_to_en" && !locked && (
        <button className="text-sm text-stone-500 underline" onClick={() => setShowTranslation((s) => !s)}>
          {showTranslation ? "Hide" : "Show"} reading help
        </button>
      )}

      {e.hints.length > 0 && !locked && e.type !== "presentation" && (
        <div className="space-y-1">
          {e.hints.slice(0, hintIndex + 1).map((h) => (
            <p key={h} className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
              <Lightbulb className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> {h}
            </p>
          ))}
          {hintIndex < e.hints.length - 1 && (
            <button className="text-sm font-medium text-amber-700" onClick={() => setHintIndex(hintIndex + 1)}>
              Show a hint
            </button>
          )}
        </div>
      )}
    </div>
  );
}
