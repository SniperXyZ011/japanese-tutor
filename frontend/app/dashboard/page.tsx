"use client";

import { ArrowRight, Flame, MessageCircle, Repeat, Target } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Card, ErrorBanner, PageHeader, ProgressBar, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { LEVEL_LABELS, type ProgressSummary, type Recommendation } from "@/lib/types";

export default function Dashboard() {
  const { profile } = useAuth();
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [prog, setProg] = useState<ProgressSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [r, p] = await Promise.all([api<Recommendation>("/recommendation"), api<ProgressSummary>("/progress")]);
      setRec(r);
      setProg(p);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const next =
    rec?.kind === "lesson" && rec.lesson ? { href: `/lessons/${rec.lesson.id}`, label: rec.lesson.title, cta: rec.lesson.status === "in_progress" ? "Continue lesson" : "Start lesson" }
    : rec?.kind === "review" ? { href: "/review", label: `${rec.due_reviews} reviews due`, cta: "Start review" }
    : rec?.kind === "assessment" ? { href: "/assessment", label: "Placement check", cta: "Take placement check" }
    : rec?.kind === "complete" ? { href: "/speak", label: "Conversation practice", cta: "Talk with your tutor" }
    : null;

  return (
    <AppShell>
      <PageHeader
        title={`おかえり${profile?.display_name ? `, ${profile.display_name}` : ""}!`}
        subtitle={profile?.current_level ? `Level: ${LEVEL_LABELS[profile.current_level]}` : "Welcome back"}
      />
      {error && <ErrorBanner message={error} onRetry={load} />}
      {!rec || !prog ? (
        !error && <Spinner />
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          <Card className="md:col-span-2 border-brand/30 bg-gradient-to-br from-white to-brand-soft">
            <p className="text-sm font-semibold uppercase tracking-wide text-brand">Today&apos;s next step</p>
            {next ? (
              <>
                <h2 className="mt-2 text-2xl font-bold">{next.label}</h2>
                <p className="mt-1 text-stone-600">{rec.reason}</p>
                <Link href={next.href} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-brand px-5 py-2.5 font-semibold text-white hover:bg-brand-dark">
                  {next.cta} <ArrowRight className="h-4 w-4" aria-hidden />
                </Link>
              </>
            ) : (
              <p className="mt-2">{rec.reason}</p>
            )}
          </Card>
          <Card>
            <div className="flex items-center gap-2 text-sm font-semibold"><Target className="h-4 w-4 text-brand" aria-hidden /> Daily goal</div>
            <p className="mt-2 text-2xl font-bold">{prog.minutes_today} / {prog.daily_goal_minutes} min</p>
            <div className="mt-2"><ProgressBar value={prog.minutes_today / Math.max(1, prog.daily_goal_minutes)} label="Daily goal" /></div>
            <div className="mt-4 flex items-center gap-2 text-sm"><Flame className="h-4 w-4 text-orange-500" aria-hidden /> {prog.streak_days}-day streak</div>
          </Card>
          <Card>
            <div className="flex items-center gap-2 text-sm font-semibold"><Repeat className="h-4 w-4 text-brand" aria-hidden /> Review</div>
            <p className="mt-2 text-2xl font-bold">{prog.reviews_due} due</p>
            <Link href="/review" className="mt-2 inline-block text-sm font-semibold text-brand">Open review queue →</Link>
          </Card>
          <Card>
            <p className="text-sm font-semibold">Lessons</p>
            <p className="mt-2 text-2xl font-bold">{prog.lessons_completed} / {prog.lessons_total}</p>
            <div className="mt-2"><ProgressBar value={prog.lessons_completed / Math.max(1, prog.lessons_total)} label="Lessons completed" /></div>
            <Link href="/learn" className="mt-2 inline-block text-sm font-semibold text-brand">See your path →</Link>
          </Card>
          <Card>
            <div className="flex items-center gap-2 text-sm font-semibold"><MessageCircle className="h-4 w-4 text-brand" aria-hidden /> Speaking room</div>
            <p className="mt-2 text-sm text-stone-600">Practise a short conversation with your AI tutor.</p>
            <Link href="/speak" className="mt-2 inline-block text-sm font-semibold text-brand">Start talking →</Link>
          </Card>
          {prog.concepts_needing_practice.length > 0 && (
            <Card className="md:col-span-3">
              <p className="text-sm font-semibold">Needs practice</p>
              <p className="mt-1 text-sm text-stone-600">{prog.concepts_needing_practice.map((c) => c.concept_id).join(", ")}</p>
            </Card>
          )}
        </div>
      )}
    </AppShell>
  );
}
