"use client";

import clsx from "clsx";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AudioButton } from "@/components/AudioButton";
import { Recorder } from "@/components/Recorder";
import { AiBadge, Button, Card, ErrorBanner, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ConversationDetail, Recap, Turn } from "@/lib/types";

export default function ConversationPage() {
  const { id } = useParams<{ id: string }>();
  const { capabilities } = useAuth();
  const [conv, setConv] = useState<ConversationDetail | null>(null);
  const [recap, setRecap] = useState<Recap | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showEn, setShowEn] = useState<Record<string, boolean>>({});
  const [inputKey, setInputKey] = useState(0);
  const bottom = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try { const c = await api<ConversationDetail>(`/conversations/${id}`); setConv(c); if (c.summary) setRecap(c.summary); }
    catch (e) { setError(errorMessage(e)); }
  }, [id]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [conv?.turns.length]);

  async function send(text: string, mode: "speech" | "typed") {
    setBusy(true); setError(null);
    try {
      const r = await api<{ learner_turn: Turn; tutor_turn: Turn }>(`/conversations/${id}/turns`, { body: { text, input_mode: mode } });
      setConv((c) => c && { ...c, turns: [...c.turns, r.learner_turn, r.tutor_turn], turn_count: r.tutor_turn.position });
      setInputKey((k) => k + 1);
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  async function finish() {
    setBusy(true);
    try { const r = await api<{ recap: Recap }>(`/conversations/${id}/finish`, { method: "POST" }); setRecap(r.recap); setConv((c) => c && { ...c, status: "completed" }); }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  if (!conv) return <AppShell>{error ? <ErrorBanner message={error} /> : <Spinner />}</AppShell>;
  const isMock = conv.provider === "mock";
  const lastTutor = [...conv.turns].reverse().find((t) => t.role === "tutor");

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl space-y-4">
        <div className="flex items-center justify-between">
          <Link href="/speak" className="flex items-center gap-1 text-sm text-stone-500"><ArrowLeft className="h-4 w-4" aria-hidden /> Speaking room</Link>
          <AiBadge isMock={isMock} provider={!isMock ? capabilities?.ai_model ?? undefined : undefined} />
        </div>
        <h1 className="text-xl font-bold">{conv.topic}</h1>
        <div className="space-y-3" aria-live="polite">
          {conv.turns.map((t) => t.role === "tutor" ? (
            <div key={t.id} className="max-w-[90%] rounded-2xl rounded-tl-sm border border-stone-200 bg-white p-4">
              <div className="flex items-start gap-2">
                <AudioButton text={t.text} size="sm" autoPlay={t.id === lastTutor?.id && conv.status === "active"} label="Play tutor message" />
                <div>
                  {t.content.reading && <p lang="ja" className="jp text-xs text-stone-500">{t.content.reading}</p>}
                  <p lang="ja" className="jp text-lg">{t.text}</p>
                  {showEn[t.id] ? <p className="text-sm text-stone-600">{t.content.english}</p> : (
                    <button className="text-xs text-stone-500 underline" onClick={() => setShowEn((s) => ({ ...s, [t.id]: true }))}>Show translation</button>
                  )}
                </div>
              </div>
              {t.content.correction?.has_error && (
                <div className="mt-3 rounded-lg bg-amber-50 p-2 text-sm">
                  <p><b>Correction:</b> <span lang="ja" className="jp">{t.content.correction.corrected}</span></p>
                  {t.content.correction.explanation && <p className="text-stone-700">{t.content.correction.explanation}</p>}
                </div>
              )}
              {!!t.content.new_vocabulary?.length && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {t.content.new_vocabulary.map((v) => (
                    <span key={v.japanese} className="rounded-full bg-stone-100 px-2 py-0.5 text-xs"><span lang="ja" className="jp">{v.japanese}</span>{v.reading ? ` (${v.reading})` : ""} — {v.meaning}</span>
                  ))}
                </div>
              )}
              {t.content.follow_up_hint && <p className="mt-2 text-xs italic text-stone-500">Hint: {t.content.follow_up_hint}</p>}
            </div>
          ) : (
            <div key={t.id} className="ml-auto max-w-[85%] rounded-2xl rounded-tr-sm bg-brand p-3 text-white">
              <p lang="ja" className="jp text-lg">{t.text}</p>
              <p className="text-xs opacity-75">{t.input_mode === "speech" ? "spoken" : "typed"}</p>
            </div>
          ))}
          {busy && <p className="text-sm text-stone-500">Tutor is thinking…</p>}
          <div ref={bottom} />
        </div>
        {error && <ErrorBanner message={error} />}
        {recap ? (
          <Card className="space-y-2">
            <h2 className="font-semibold">Conversation recap</h2>
            <p>{recap.summary}</p>
            {recap.strengths.length > 0 && <div><p className="text-sm font-semibold">What went well</p><ul className="list-inside list-disc text-sm">{recap.strengths.map((s) => <li key={s}>{s}</li>)}</ul></div>}
            {recap.improvements.length > 0 && <div><p className="text-sm font-semibold">To work on</p><ul className="list-inside list-disc text-sm">{recap.improvements.map((s) => <li key={s}>{s}</li>)}</ul></div>}
            {recap.vocabulary.length > 0 && <p className="text-sm"><b>Vocabulary:</b> {recap.vocabulary.map((v) => `${v.japanese} (${v.meaning})`).join(", ")}</p>}
          </Card>
        ) : conv.status === "active" ? (
          <Card className="space-y-3">
            <Recorder key={inputKey} disabled={busy} submitLabel="Send" onSubmit={send} />
            <div className="flex justify-end">
              <Button variant="ghost" onClick={finish} disabled={busy || conv.turns.length < 3}>End & get recap</Button>
            </div>
          </Card>
        ) : null}
        <p className={clsx("text-xs text-stone-400")}>Speaking feedback is based on what your browser recognised, not on pronunciation analysis.</p>
      </div>
    </AppShell>
  );
}
