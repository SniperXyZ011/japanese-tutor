"use client";

import clsx from "clsx";
import { CheckCircle2, Circle, Lock, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Card, ErrorBanner, PageHeader, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { Unit } from "@/lib/types";

export default function LearnPage() {
  const [units, setUnits] = useState<Unit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setError(null);
    try { setUnits(await api<Unit[]>("/curriculum")); } catch (e) { setError(errorMessage(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <AppShell>
      <PageHeader title="Your learning path" subtitle="Beginner curriculum aligned with JLPT N5. Lessons unlock as you complete their prerequisites." />
      {error && <ErrorBanner message={error} onRetry={load} />}
      {!units ? !error && <Spinner /> : (
        <div className="space-y-6">
          {units.map((u) => (
            <Card key={u.id}>
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">Unit {u.position} · {u.level}</p>
              <h2 className="text-lg font-bold">{u.title}</h2>
              <p className="text-sm text-stone-600">{u.description}</p>
              <ul className="mt-4 divide-y divide-stone-100">
                {u.lessons.map((l) => {
                  const Icon = l.locked ? Lock : l.status === "completed" ? CheckCircle2 : l.status === "in_progress" ? PlayCircle : Circle;
                  const inner = (
                    <div className={clsx("flex items-center gap-3 py-3", l.locked && "opacity-50")}>
                      <Icon className={clsx("h-5 w-5 shrink-0", l.status === "completed" ? "text-emerald-600" : "text-brand")} aria-hidden />
                      <div className="flex-1">
                        <p className="font-medium">{l.title}</p>
                        <p className="text-sm text-stone-500">{l.summary}</p>
                      </div>
                      <div className="text-right text-xs text-stone-500">
                        <p>{l.estimated_minutes} min</p>
                        {l.best_score !== null && <p>Best {Math.round(l.best_score * 100)}%</p>}
                        {l.locked && <p>Locked</p>}
                      </div>
                    </div>
                  );
                  return (
                    <li key={l.id}>
                      {l.locked ? inner : <Link href={`/lessons/${l.id}`} className="block rounded-lg hover:bg-stone-50">{inner}</Link>}
                    </li>
                  );
                })}
              </ul>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
}
