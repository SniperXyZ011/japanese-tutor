"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AiBadge, Button, Card, ErrorBanner, PageHeader, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Conversation, ConversationDetail } from "@/lib/types";

const TOPICS = ["Self-introduction", "Ordering at a café", "Hobbies and likes", "Asking for directions", "Weekend plans", "Shopping"];

export default function SpeakPage() {
  const { capabilities } = useAuth();
  const router = useRouter();
  const [list, setList] = useState<Conversation[] | null>(null);
  const [topic, setTopic] = useState(TOPICS[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setList((await api<{ items: Conversation[] }>("/conversations")).items); } catch (e) { setError(errorMessage(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function start() {
    setBusy(true); setError(null);
    try {
      const c = await api<ConversationDetail>("/conversations", { body: { topic, mode: "free_conversation" } });
      router.push(`/speak/${c.id}`);
    } catch (e) { setError(errorMessage(e)); setBusy(false); }
  }

  const aiOff = capabilities?.ai_provider === "none";
  return (
    <AppShell>
      <PageHeader title="Speaking room" subtitle="Short conversations with your AI tutor, at your level."
        action={capabilities && !aiOff ? <AiBadge isMock={capabilities.ai_is_mock} provider={capabilities.ai_model ?? undefined} /> : undefined} />
      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
      <Card className="space-y-4">
        <h2 className="font-semibold">Start a conversation</h2>
        {aiOff ? <p className="text-sm text-stone-600">The AI tutor isn&apos;t configured on this server. Lessons and review still work.</p> : (
          <>
            <div className="flex flex-wrap gap-2">
              {TOPICS.map((t) => (
                <button key={t} onClick={() => setTopic(t)} className={`rounded-full border px-3 py-1 text-sm ${topic === t ? "border-brand bg-brand-soft text-brand" : "border-stone-300"}`}>{t}</button>
              ))}
            </div>
            <input value={topic} onChange={(e) => setTopic(e.target.value)} maxLength={120} aria-label="Custom topic" className="w-full max-w-md rounded-xl border border-stone-300 px-3 py-2" />
            <Button onClick={start} loading={busy} disabled={!topic.trim()}>Start talking</Button>
          </>
        )}
      </Card>
      <h2 className="mb-2 mt-8 font-semibold">Past conversations</h2>
      {!list ? <Spinner /> : list.length === 0 ? <p className="text-sm text-stone-500">None yet.</p> : (
        <ul className="space-y-2">
          {list.map((c) => (
            <li key={c.id}>
              <Link href={`/speak/${c.id}`} className="flex justify-between rounded-xl border border-stone-200 bg-white p-3 hover:bg-stone-50">
                <span className="font-medium">{c.topic}</span>
                <span className="text-sm text-stone-500">{c.turn_count} turns · {c.status === "completed" ? "finished" : "active"} · {new Date(c.created_at).toLocaleDateString()}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}
