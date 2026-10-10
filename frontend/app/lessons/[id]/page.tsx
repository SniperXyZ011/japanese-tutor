"use client";

import { ArrowLeft, ArrowRight, BookOpen, Eye, EyeOff } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AudioButton } from "@/components/AudioButton";
import { ExerciseView } from "@/components/ExerciseView";
import { FeedbackCard } from "@/components/FeedbackCard";
import { Button, Card, ErrorBanner, ProgressBar, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AttemptResult, Evaluation, LessonComplete, LessonDetail } from "@/lib/types";

export default function LessonPage() {
  const { id } = useParams<{ id: string }>();
  const { profile } = useAuth();
  const [lesson, setLesson] = useState<LessonDetail | null>(null);
  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [step, setStep] = useState(-1); // -1 = intro
  const [feedback, setFeedback] = useState<Record<string, Evaluation>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<LessonComplete | null>(null);
  const [showReading, setShowReading] = useState(true);
  const [showRomaji, setShowRomaji] = useState(false);
  const started = useRef<number>(Date.now());

  useEffect(() => {
    if (profile) { setShowReading(profile.show_furigana); setShowRomaji(profile.show_romaji); }
  }, [profile]);

  const load = useCallback(async () => {
    setError(null);
    try {
      const l = await api<LessonDetail>(`/lessons/${id}`);
      setLesson(l);
      if (l.attempt_id) { setAttemptId(l.attempt_id); }
    } catch (e) { setError(errorMessage(e)); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  async function begin(resume: boolean) {
    setBusy(true);
    try {
      const s = await api<{ attempt_id: string; current_step: number }>(`/lessons/${id}/start`, { method: "POST" });
      setAttemptId(s.attempt_id);
      started.current = Date.now();
      setStep(resume ? Math.min(s.current_step, (lesson?.exercises.length ?? 1) - 1) : 0);
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  async function submit(answer: string, mode: "typed" | "speech" | "choice", usedHint: boolean) {
    if (!lesson) return;
    const ex = lesson.exercises[step];
    setBusy(true);
    setError(null);
    try {
      const r = await api<AttemptResult>(`/exercises/${ex.id}/attempt`, {
        body: { answer, input_mode: mode, used_hint: usedHint, lesson_attempt_id: attemptId },
      });
      setFeedback((f) => ({ ...f, [ex.id]: r.evaluation }));
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  async function next() {
    if (!lesson || !attemptId) return;
    if (step < lesson.exercises.length - 1) {
      const n = step + 1;
      setStep(n);
      api(`/lessons/${id}/progress?attempt_id=${attemptId}&step=${n}`, { method: "POST" }).catch(() => undefined);
      return;
    }
    setBusy(true);
    try {
      const seconds = Math.round((Date.now() - started.current) / 1000);
      setDone(await api<LessonComplete>(`/lessons/${id}/complete`, { body: { attempt_id: attemptId, active_seconds: seconds } }));
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  if (!lesson) return <AppShell>{error ? <ErrorBanner message={error} onRetry={load} /> : <Spinner />}</AppShell>;

  if (done) {
    return (
      <AppShell>
        <Card className="mx-auto max-w-xl space-y-4 text-center">
          <p lang="ja" className="jp text-4xl">{done.passed ? "よくできました！" : "がんばりましょう！"}</p>
          <h1 className="text-xl font-bold">{done.passed ? "Lesson complete" : "Lesson finished — worth another try"}</h1>
          <p className="text-3xl font-bold text-brand">{Math.round(done.score * 100)}%</p>
          <p className="text-stone-600">{done.exercises_answered} exercises answered. Missed items were added to your review queue.</p>
          <div className="flex flex-wrap justify-center gap-2">
            {done.next.kind === "lesson" && done.next.lesson && done.next.lesson.id !== lesson.id && (
              <Link href={`/lessons/${done.next.lesson.id}`} onClick={() => location.assign(`/lessons/${done.next.lesson!.id}`)}
                className="rounded-xl bg-brand px-5 py-2.5 font-semibold text-white">Next: {done.next.lesson.title}</Link>
            )}
            {done.next.kind === "review" && <Link href="/review" className="rounded-xl bg-brand px-5 py-2.5 font-semibold text-white">Review now</Link>}
            <Link href="/dashboard" className="rounded-xl border border-stone-300 bg-white px-5 py-2.5 font-semibold">Back to dashboard</Link>
          </div>
        </Card>
      </AppShell>
    );
  }

  if (step < 0) {
    const resumable = lesson.attempt_id && lesson.current_step > 0;
    return (
      <AppShell>
        <Link href="/learn" className="mb-4 inline-flex items-center gap-1 text-sm text-stone-500"><ArrowLeft className="h-4 w-4" aria-hidden /> Learning path</Link>
        <Card className="space-y-5">
          <div>
            <p className="text-sm text-stone-500">{lesson.estimated_minutes} min · difficulty {lesson.difficulty}</p>
            <h1 className="text-2xl font-bold">{lesson.title}</h1>
            <p className="text-stone-600">{lesson.summary}</p>
          </div>
          <div>
            <p className="mb-1 font-semibold">You will learn to</p>
            <ul className="list-inside list-disc text-stone-700">{lesson.objectives.map((o) => <li key={o}>{o}</li>)}</ul>
          </div>
          {lesson.vocabulary.length > 0 && (
            <div>
              <p className="mb-2 flex items-center gap-2 font-semibold"><BookOpen className="h-4 w-4" aria-hidden /> Vocabulary</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {lesson.vocabulary.map((v) => (
                  <div key={v.id} className="flex items-center gap-3 rounded-xl border border-stone-200 p-2">
                    <AudioButton text={v.japanese.replace("〜", "")} size="sm" label={`Play ${v.japanese}`} />
                    <div>
                      <p lang="ja" className="jp font-semibold">{v.japanese} {v.reading !== v.japanese && <span className="text-sm font-normal text-stone-500">{v.reading}</span>}</p>
                      <p className="text-sm text-stone-600">{v.meaning}{showRomaji && ` · ${v.romaji}`}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {lesson.grammar.map((g) => (
            <div key={g.id} className="rounded-xl bg-stone-50 p-4">
              <p className="font-semibold">{g.name} <span lang="ja" className="jp ml-2 text-sm text-stone-500">{g.pattern}</span></p>
              <p className="mt-1 text-sm text-stone-700">{g.explanation}</p>
              {g.examples.map((ex) => (
                <div key={ex.japanese} className="mt-2 flex items-center gap-2">
                  <AudioButton text={ex.japanese} size="sm" label={`Play ${ex.japanese}`} />
                  <span lang="ja" className="jp">{ex.japanese}</span><span className="text-sm text-stone-500">— {ex.english}</span>
                </div>
              ))}
            </div>
          ))}
          {error && <ErrorBanner message={error} />}
          <div className="flex flex-wrap gap-2">
            {resumable && <Button onClick={() => begin(true)} loading={busy}>Resume (step {lesson.current_step + 1})</Button>}
            <Button variant={resumable ? "secondary" : "primary"} onClick={() => begin(false)} loading={busy}>
              {resumable ? "Start over" : lesson.status === "completed" ? "Practise again" : "Start lesson"}
            </Button>
          </div>
        </Card>
      </AppShell>
    );
  }

  const ex = lesson.exercises[step];
  const fb = feedback[ex.id];
  const canAdvance = ex.type === "presentation" || !!fb;
  return (
    <AppShell>
      <div className="mx-auto max-w-2xl space-y-4">
        <div className="flex items-center gap-3">
          <Link href="/learn" aria-label="Exit lesson" className="text-stone-500"><ArrowLeft className="h-5 w-5" aria-hidden /></Link>
          <ProgressBar value={(step + (canAdvance ? 1 : 0)) / lesson.exercises.length} label="Lesson progress" />
          <span className="text-sm text-stone-500">{step + 1}/{lesson.exercises.length}</span>
        </div>
        <div className="flex justify-end gap-3 text-xs">
          <button onClick={() => setShowReading((s) => !s)} className="flex items-center gap-1 text-stone-500">
            {showReading ? <EyeOff className="h-3 w-3" aria-hidden /> : <Eye className="h-3 w-3" aria-hidden />} Furigana
          </button>
          <button onClick={() => setShowRomaji((s) => !s)} className="flex items-center gap-1 text-stone-500">
            {showRomaji ? <EyeOff className="h-3 w-3" aria-hidden /> : <Eye className="h-3 w-3" aria-hidden />} Romaji
          </button>
        </div>
        <Card>
          <ExerciseView key={ex.id} exercise={ex} onSubmit={submit} busy={busy} locked={!!fb} showReading={showReading} showRomaji={showRomaji} />
          {ex.type === "presentation" && typeof ex.meta?.note === "string" && <p className="mt-3 text-sm text-stone-600">{ex.meta.note}</p>}
        </Card>
        {fb && <FeedbackCard evaluation={fb} />}
        {error && <ErrorBanner message={error} />}
        <div className="flex justify-between">
          <Button variant="ghost" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>Back</Button>
          {fb && !fb.is_correct && (
            <Button variant="secondary" onClick={() => setFeedback((f) => { const c = { ...f }; delete c[ex.id]; return c; })}>Try again</Button>
          )}
          <Button onClick={next} disabled={!canAdvance} loading={busy && canAdvance}>
            {step === lesson.exercises.length - 1 ? "Finish lesson" : "Continue"} <ArrowRight className="h-4 w-4" aria-hidden />
          </Button>
        </div>
      </div>
    </AppShell>
  );
}
