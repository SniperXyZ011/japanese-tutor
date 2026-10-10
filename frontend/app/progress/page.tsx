"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Card, ErrorBanner, PageHeader, ProgressBar, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { LEVEL_LABELS, type HistoryItem, type ProgressSummary, type SkillProgress } from "@/lib/types";

export default function ProgressPage() {
  const [p, setP] = useState<ProgressSummary | null>(null);
  const [skills, setSkills] = useState<SkillProgress[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setError(null);
    try {
      const [a, b, c] = await Promise.all([api<ProgressSummary>("/progress"), api<SkillProgress[]>("/progress/skills"), api<HistoryItem[]>("/history")]);
      setP(a); setSkills(b); setHistory(c);
    } catch (e) { setError(errorMessage(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <AppShell>
      <PageHeader title="Progress" subtitle={p?.current_level ? `Current level: ${LEVEL_LABELS[p.current_level]}` : undefined} />
      {error && <ErrorBanner message={error} onRetry={load} />}
      {!p ? !error && <Spinner /> : (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["Lessons", `${p.lessons_completed}/${p.lessons_total}`],
              ["Accuracy", p.accuracy === null ? "—" : `${Math.round(p.accuracy * 100)}%`],
              ["Study time", `${p.learning_minutes} min`],
              ["Streak", `${p.streak_days} days`],
              ["Exercises", String(p.exercises_answered)],
              ["Reviews done", String(p.reviews_completed)],
              ["Reviews due", String(p.reviews_due)],
              ["Today", `${p.minutes_today}/${p.daily_goal_minutes} min`],
            ].map(([k, v]) => (
              <Card key={k}><p className="text-sm text-stone-500">{k}</p><p className="text-2xl font-bold">{v}</p></Card>
            ))}
          </div>
          <Card>
            <h2 className="mb-3 font-semibold">Skills</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {skills.map((s) => (
                <div key={s.skill}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="capitalize">{s.skill}</span>
                    <span className="text-stone-500">
                      {s.mastery !== null ? `mastery ${Math.round(s.mastery * 100)}%` : "no practice yet"}
                      {s.accuracy !== null && ` · ${Math.round(s.accuracy * 100)}% correct (${s.attempts})`}
                    </span>
                  </div>
                  <ProgressBar value={s.mastery ?? s.placement_score ?? 0} label={`${s.skill} mastery`} />
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-stone-500">Speaking accuracy reflects speech-recognition transcripts, not a pronunciation score.</p>
          </Card>
          {p.recent_mistakes.length > 0 && (
            <Card>
              <h2 className="mb-2 font-semibold">Recent mistakes</h2>
              <ul className="space-y-2 text-sm">
                {p.recent_mistakes.map((m) => (
                  <li key={m.exercise_id + m.created_at} className="rounded-lg bg-stone-50 p-2">
                    <p className="text-stone-600">{m.instructions}</p>
                    <p><span className="jp text-red-700 line-through" lang="ja">{m.answer}</span> → <span className="jp font-semibold" lang="ja">{m.expected}</span></p>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <Card>
            <h2 className="mb-2 font-semibold">History</h2>
            {history.length === 0 ? <p className="text-sm text-stone-500">No activity yet.</p> : (
              <ul className="divide-y divide-stone-100 text-sm">
                {history.map((h, k) => (
                  <li key={k} className="flex justify-between py-2">
                    <span><span className="mr-2 rounded bg-stone-100 px-1.5 py-0.5 text-xs capitalize">{h.kind}</span>{h.title}</span>
                    <span className="text-stone-500">{h.detail} · {new Date(h.created_at).toLocaleDateString()}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </AppShell>
  );
}
