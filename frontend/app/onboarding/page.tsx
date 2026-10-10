"use client";

import clsx from "clsx";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button, Card, ErrorBanner, ProgressBar } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { OnboardingAnswers, Profile } from "@/lib/types";

type Key = keyof OnboardingAnswers;
interface Step {
  key: Key;
  title: string;
  multi?: boolean;
  options: { value: string | number; label: string }[];
}

const STEPS: Step[] = [
  { key: "prior_experience", title: "Have you studied Japanese before?", options: [
    { value: "none", label: "Never — I'm brand new" }, { value: "some_self_study", label: "A little self-study (apps, videos)" },
    { value: "classes", label: "I've taken classes" }, { value: "lived_in_japan", label: "I've lived in or visited Japan a lot" }] },
  { key: "hiragana", title: "Can you read hiragana (あいう)?", options: [
    { value: "none", label: "Not yet" }, { value: "some", label: "Some characters" }, { value: "fluent", label: "Yes, comfortably" }] },
  { key: "katakana", title: "Can you read katakana (アイウ)?", options: [
    { value: "none", label: "Not yet" }, { value: "some", label: "Some characters" }, { value: "fluent", label: "Yes, comfortably" }] },
  { key: "kanji", title: "How much kanji (日本) do you know?", options: [
    { value: "none", label: "None" }, { value: "few", label: "A few basic ones" }, { value: "n5", label: "Around JLPT N5 (~100)" }, { value: "n4_plus", label: "More than that" }] },
  { key: "listening", title: "How well can you understand spoken Japanese?", options: [
    { value: "none", label: "Not at all" }, { value: "basic_phrases", label: "Basic phrases" }, { value: "slow_conversation", label: "Slow, simple conversation" }, { value: "everyday", label: "Most everyday conversation" }] },
  { key: "speaking_confidence", title: "How confident do you feel speaking?", options: [
    { value: "none", label: "I've never tried" }, { value: "low", label: "Nervous, only a few words" }, { value: "medium", label: "I can manage simple exchanges" }, { value: "high", label: "Fairly confident" }] },
  { key: "vocab_grammar", title: "What's your grammar & vocabulary level?", options: [
    { value: "none", label: "Nothing yet" }, { value: "basic", label: "Basics (です, a few words)" }, { value: "n5", label: "Around JLPT N5" }, { value: "n4_plus", label: "N4 or above" }] },
  { key: "goals", title: "Why are you learning? (choose any)", multi: true, options: [
    { value: "travel", label: "Travel" }, { value: "anime_media", label: "Anime, games & media" }, { value: "work", label: "Work" },
    { value: "jlpt", label: "JLPT exam" }, { value: "friends_family", label: "Friends or family" }, { value: "culture", label: "Culture & curiosity" }, { value: "moving", label: "Moving to Japan" }] },
  { key: "daily_minutes", title: "How much time can you study each day?", options: [
    { value: 5, label: "5 minutes" }, { value: 10, label: "10 minutes" }, { value: 15, label: "15 minutes" }, { value: 30, label: "30 minutes" }, { value: 60, label: "60 minutes" }] },
  { key: "conversation_balance", title: "How do you like to learn?", options: [
    { value: "more_structured", label: "Mostly structured lessons" }, { value: "balanced", label: "A balance" }, { value: "more_conversation", label: "Lots of conversation practice" }] },
];

export default function OnboardingPage() {
  const { profile, setProfile } = useAuth();
  const router = useRouter();
  const [i, setI] = useState(0);
  const [answers, setAnswers] = useState<OnboardingAnswers>({ goals: [], ...(profile?.onboarding ?? {}) } as OnboardingAnswers);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const step = STEPS[i];
  const value = answers[step.key];
  const answered = step.multi ? (value as string[]).length > 0 : value !== undefined && value !== null;

  function choose(v: string | number) {
    if (step.multi) {
      const cur = (answers.goals ?? []) as string[];
      setAnswers({ ...answers, goals: cur.includes(v as string) ? cur.filter((x) => x !== v) : [...cur, v as string] });
    } else setAnswers({ ...answers, [step.key]: v });
  }

  async function finish(takeAssessment: boolean) {
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { onboarding: answers, onboarding_completed: true };
      if (!takeAssessment) body.current_level = "absolute_beginner";
      const p = await api<Profile>("/me", { method: "PATCH", body });
      setProfile(p);
      router.replace(takeAssessment ? "/assessment" : "/dashboard");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const last = i === STEPS.length - 1;
  return (
    <AppShell requireOnboarding={false}>
      <div className="mx-auto max-w-xl">
        <p className="mb-2 text-sm text-stone-500">Step {i + 1} of {STEPS.length}</p>
        <ProgressBar value={(i + 1) / STEPS.length} label="Onboarding progress" />
        <Card className="mt-6">
          <h1 className="mb-4 text-xl font-bold">{step.title}</h1>
          <div className="grid gap-2" role={step.multi ? "group" : "radiogroup"} aria-label={step.title}>
            {step.options.map((o) => {
              const selected = step.multi ? (value as string[]).includes(o.value as string) : value === o.value;
              return (
                <button key={String(o.value)} type="button" onClick={() => choose(o.value)}
                  role={step.multi ? "checkbox" : "radio"} aria-checked={selected}
                  className={clsx("rounded-xl border px-4 py-3 text-left transition",
                    selected ? "border-brand bg-brand-soft font-semibold text-brand" : "border-stone-200 hover:border-stone-400")}>
                  {o.label}
                </button>
              );
            })}
          </div>
          {error && <div className="mt-4"><ErrorBanner message={error} /></div>}
          <div className="mt-6 flex flex-wrap justify-between gap-2">
            <Button variant="ghost" onClick={() => setI(i - 1)} disabled={i === 0}>Back</Button>
            {!last ? (
              <Button onClick={() => setI(i + 1)} disabled={!answered}>Continue</Button>
            ) : (
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => finish(false)} loading={busy}>Start from scratch</Button>
                <Button onClick={() => finish(true)} loading={busy} disabled={!answered}>Take placement check (~5 min)</Button>
              </div>
            )}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
