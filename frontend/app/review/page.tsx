"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AudioButton } from "@/components/AudioButton";
import { Button, Card, ErrorBanner, PageHeader, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { ReviewCard } from "@/lib/types";

const GRADES = [
  { g: "again", label: "Again", hint: "Forgot", cls: "bg-red-600 hover:bg-red-700" },
  { g: "hard", label: "Hard", hint: "Struggled", cls: "bg-amber-600 hover:bg-amber-700" },
  { g: "good", label: "Good", hint: "Remembered", cls: "bg-emerald-600 hover:bg-emerald-700" },
  { g: "easy", label: "Easy", hint: "Instant", cls: "bg-sky-600 hover:bg-sky-700" },
] as const;

export default function ReviewPage() {
  const [cards, setCards] = useState<ReviewCard[] | null>(null);
  const [due, setDue] = useState(0);
  const [i, setI] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [reviewed, setReviewed] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const q = await api<{ due_count: number; items: ReviewCard[] }>("/review");
      setCards(q.items); setDue(q.due_count); setI(0); setRevealed(false);
    } catch (e) { setError(errorMessage(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function grade(g: string) {
    if (!cards) return;
    setBusy(true);
    try {
      await api("/review", { body: { review_id: cards[i].id, grade: g } });
      setReviewed((n) => n + 1);
      setRevealed(false);
      if (i + 1 < cards.length) setI(i + 1); else await load();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  const card = cards?.[i];
  return (
    <AppShell>
      <PageHeader title="Review" subtitle={`${due} due now${reviewed ? ` · ${reviewed} reviewed this session` : ""}`} />
      {error && <ErrorBanner message={error} onRetry={load} />}
      {!cards ? !error && <Spinner /> : !card ? (
        <Card className="text-center">
          <p lang="ja" className="jp text-3xl">おつかれさま！</p>
          <p className="mt-2 text-stone-600">Nothing due right now. Items you get wrong come back within minutes; items you know come back days later.</p>
          <Link href="/learn" className="mt-4 inline-block font-semibold text-brand">Continue learning →</Link>
        </Card>
      ) : (
        <Card className="mx-auto max-w-lg space-y-5 text-center">
          <div className="flex justify-center gap-2 text-xs text-stone-500">
            <span className="rounded-full bg-stone-100 px-2 py-0.5 capitalize">{card.concept_type}</span>
            {card.from_mistake && <span className="rounded-full bg-red-100 px-2 py-0.5 text-red-700">from a mistake</span>}
          </div>
          <p lang="ja" className="jp text-5xl font-semibold">{card.front}</p>
          {card.audio_text && <div className="flex justify-center"><AudioButton key={card.id} text={card.audio_text} size="lg" /></div>}
          {revealed ? (
            <div className="space-y-2">
              {card.reading && <p lang="ja" className="jp text-xl text-stone-600">{card.reading}</p>}
              <p className="text-2xl font-bold">{card.meaning}</p>
              {card.detail && <p className="text-sm text-stone-600">{card.detail}</p>}
              <p className="pt-2 text-sm text-stone-500">How well did you remember?</p>
              <div className="grid grid-cols-4 gap-2">
                {GRADES.map((x) => (
                  <button key={x.g} disabled={busy} onClick={() => grade(x.g)} className={`rounded-xl px-2 py-2 text-white ${x.cls} disabled:opacity-50`}>
                    <span className="block font-semibold">{x.label}</span><span className="text-xs opacity-80">{x.hint}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <Button onClick={() => setRevealed(true)} className="w-full">Show answer</Button>
          )}
          <p className="text-xs text-stone-400">{i + 1} of {cards.length}</p>
        </Card>
      )}
    </AppShell>
  );
}
