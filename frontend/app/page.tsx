"use client";

import { Headphones, Mic, Repeat, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const { profile, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!loading && profile) router.replace("/dashboard");
  }, [loading, profile, router]);

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-16">
      <p lang="ja" className="jp text-5xl font-bold text-brand">ことば</p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">Your personal AI Japanese tutor</h1>
      <p className="mt-4 max-w-2xl text-lg text-stone-600">
        Listen, understand, speak, get feedback — then review at just the right time. Built for English speakers
        starting from zero up to JLPT N5.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link href="/signup" className="rounded-xl bg-brand px-6 py-3 font-semibold text-white hover:bg-brand-dark">
          Start learning — free
        </Link>
        <Link href="/login" className="rounded-xl border border-stone-300 bg-white px-6 py-3 font-semibold hover:bg-stone-50">
          Sign in
        </Link>
      </div>
      <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { icon: Headphones, t: "Listen", d: "Native-speed and slow audio for every phrase." },
          { icon: Mic, t: "Speak", d: "Answer out loud and get instant feedback." },
          { icon: Sparkles, t: "AI tutor", d: "Practise real conversations at your level." },
          { icon: Repeat, t: "Review", d: "Spaced repetition brings back what you miss." },
        ].map(({ icon: Icon, t, d }) => (
          <div key={t} className="rounded-2xl border border-stone-200 bg-white p-4">
            <Icon className="h-5 w-5 text-brand" aria-hidden />
            <p className="mt-2 font-semibold">{t}</p>
            <p className="text-sm text-stone-600">{d}</p>
          </div>
        ))}
      </div>
    </main>
  );
}
