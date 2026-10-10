"use client";

import clsx from "clsx";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AudioButton } from "@/components/AudioButton";
import { Recorder } from "@/components/Recorder";
import { Button, Card, ErrorBanner, PageHeader, ProgressBar, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AssessmentProgress, PlacementResult } from "@/lib/types";

export default function AssessmentPage() {
  const { refresh } = useAuth();
  const [progress, setProgress] = useState<AssessmentProgress | null>(null);
  const [result, setResult] = useState<PlacementResult | null>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setProgress(await api<AssessmentProgress>("/assessment/start", { body: {} }));
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function submit(answer: string, mode: "choice" | "typed" | "speech", skipped = false) {
    if (!progress?.next_item) return;
    setBusy(true);
    setError(null);
    try {
      const p = await api<AssessmentProgress>(`/assessment/${progress.assessment_id}/answer`, {
        body: { item_id: progress.next_item.id, answer, input_mode: mode, skipped },
      });
      setTyped("");
      setProgress(p);
      if (p.status === "completed") {
        setResult(await api<PlacementResult>(`/assessment/${p.assessment_id}/result`));
        await refresh();
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function finishEarly() {
    if (!progress) return;
    setBusy(true);
    try {
      setResult(await api<PlacementResult>(`/assessment/${progress.assessment_id}/finish`, { method: "POST" }));
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <AppShell>
        <PageHeader title="Your placement" subtitle={result.disclaimer} />
        <Card className="space-y-4">
          <div>
            <p className="text-sm text-stone-500">Recommended starting level</p>
            <p className="text-2xl font-bold text-brand">{result.recommended_level_label}</p>
          </div>
          <p>{result.explanation}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {result.skills.map((s) => (
              <div key={s.skill}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="capitalize">{s.skill}</span>
                  <span className="text-stone-500">{s.items ? `${Math.round(s.score * 100)}%` : "not tested"}{s.items > 0 && s.confidence < 0.5 ? " · low confidence" : ""}</span>
                </div>
                <ProgressBar value={s.score} label={`${s.skill} estimate`} />
              </div>
            ))}
          </div>
          {result.strengths.length > 0 && <p className="text-sm"><b>Strengths:</b> {result.strengths.join(", ")}</p>}
          {result.weak_areas.length > 0 && <p className="text-sm"><b>Focus areas:</b> {result.weak_areas.join(", ")}</p>}
          <Link href="/dashboard" className="inline-block rounded-xl bg-brand px-5 py-2.5 font-semibold text-white">Go to my path</Link>
        </Card>
      </AppShell>
    );
  }

  const item = progress?.next_item;
  return (
    <AppShell>
      <PageHeader title="Placement check" subtitle="Short and adaptive. It's fine to skip anything you don't know — no answers are shown during the check." />
      {error && <div className="mb-4"><ErrorBanner message={error} onRetry={progress ? undefined : load} /></div>}
      {!progress ? (
        !error && <Spinner />
      ) : item ? (
        <Card className="space-y-5">
          <div className="flex items-center justify-between text-sm text-stone-500">
            <span className="capitalize">{item.skill}</span>
            <span>Question {progress.answered + 1} of ~{progress.estimated_total}</span>
          </div>
          <ProgressBar value={progress.answered / Math.max(1, progress.estimated_total)} label="Assessment progress" />
          <h2 className="text-lg font-semibold">{item.instructions}</h2>
          {item.audio_text && (
            <div className="flex items-center gap-3">
              <AudioButton key={item.id} text={item.audio_text} size="lg" autoPlay label="Play question audio" />
              <AudioButton text={item.audio_text} rate={0.7} size="sm" label="Play slowly" />
              <span className="text-sm text-stone-500">Replay or slow down as needed</span>
            </div>
          )}
          {item.prompt_ja && <p lang="ja" className="jp text-4xl font-semibold">{item.prompt_ja}</p>}
          {item.prompt_en && !item.choices.length && <p className="text-lg">“{item.prompt_en}”</p>}
          {item.choices.length > 0 ? (
            <div className="grid gap-2 sm:grid-cols-2">
              {item.choices.map((c) => (
                <button key={c} disabled={busy} onClick={() => submit(c, "choice")}
                  className={clsx("jp rounded-xl border border-stone-200 px-4 py-3 text-left text-lg hover:border-brand hover:bg-brand-soft disabled:opacity-50")}>
                  {c}
                </button>
              ))}
            </div>
          ) : item.type === "speaking" ? (
            <Recorder key={item.id} disabled={busy} submitLabel="Submit" onSubmit={(t, m) => submit(t, m)} />
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); if (typed.trim()) submit(typed.trim(), "typed"); }} className="space-y-3">
              <input lang="ja" value={typed} onChange={(e) => setTyped(e.target.value)} aria-label="Your answer"
                placeholder="日本語で入力…" className="jp w-full rounded-xl border border-stone-300 px-4 py-3 text-lg focus:border-brand focus:outline-none" />
              <Button type="submit" loading={busy} disabled={!typed.trim()}>Submit</Button>
            </form>
          )}
          <div className="flex flex-wrap justify-between gap-2 border-t border-stone-100 pt-4">
            <Button variant="ghost" onClick={() => submit("", "typed", true)} disabled={busy}>I don&apos;t know — skip</Button>
            <Button variant="ghost" onClick={finishEarly} disabled={busy || progress.answered < 3}>Finish now</Button>
          </div>
        </Card>
      ) : (
        <Spinner label="Calculating your placement…" />
      )}
    </AppShell>
  );
}
