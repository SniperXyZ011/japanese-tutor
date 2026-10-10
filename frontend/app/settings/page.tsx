"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AudioButton } from "@/components/AudioButton";
import { AiBadge, Button, Card, ErrorBanner, PageHeader } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useJapaneseVoices } from "@/lib/speech";
import type { Profile } from "@/lib/types";

export default function SettingsPage() {
  const { profile, setProfile, capabilities, signOut } = useAuth();
  const voices = useJapaneseVoices();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  if (!profile) return <AppShell>{null}</AppShell>;

  async function update(patch: Partial<Profile>) {
    setError(null); setSaved(false);
    try { setProfile(await api<Profile>("/me", { method: "PATCH", body: patch })); setSaved(true); }
    catch (e) { setError(errorMessage(e)); }
  }

  async function deleteAccount() {
    try { await api("/me", { method: "DELETE" }); await signOut(); router.replace("/"); }
    catch (e) { setError(errorMessage(e)); }
  }

  return (
    <AppShell>
      <PageHeader title="Settings" />
      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
      {saved && <p className="mb-4 text-sm text-emerald-700" role="status">Saved.</p>}
      <div className="space-y-4">
        <Card className="space-y-4">
          <h2 className="font-semibold">Profile</h2>
          <label className="block text-sm">Display name
            <input defaultValue={profile.display_name ?? ""} maxLength={80} onBlur={(e) => e.target.value !== (profile.display_name ?? "") && update({ display_name: e.target.value })}
              className="mt-1 w-full max-w-sm rounded-xl border border-stone-300 px-3 py-2" />
          </label>
          <label className="block text-sm">Daily goal (minutes)
            <select value={profile.daily_goal_minutes} onChange={(e) => update({ daily_goal_minutes: Number(e.target.value) })} className="mt-1 block rounded-xl border border-stone-300 px-3 py-2">
              {[5, 10, 15, 20, 30, 45, 60].map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
          <Button variant="secondary" onClick={() => router.push("/assessment")}>Retake placement check</Button>
        </Card>
        <Card className="space-y-4">
          <h2 className="font-semibold">Audio & display</h2>
          <label className="block text-sm">Playback speed: {profile.playback_speed.toFixed(2)}×
            <input type="range" min={0.5} max={1.5} step={0.05} defaultValue={profile.playback_speed}
              onMouseUp={(e) => update({ playback_speed: Number((e.target as HTMLInputElement).value) })}
              onTouchEnd={(e) => update({ playback_speed: Number((e.target as HTMLInputElement).value) })}
              onKeyUp={(e) => update({ playback_speed: Number((e.target as HTMLInputElement).value) })}
              className="mt-1 block w-full max-w-sm accent-orange-700" />
          </label>
          <div className="flex items-end gap-3">
            <label className="block text-sm">Japanese voice
              <select value={profile.voice_name ?? ""} onChange={(e) => update({ voice_name: e.target.value || null })} className="mt-1 block rounded-xl border border-stone-300 px-3 py-2">
                <option value="">Browser default</option>
                {voices.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}
              </select>
            </label>
            <AudioButton text="こんにちは、よろしくお願いします。" label="Test voice" />
          </div>
          {voices.length === 0 && <p className="text-xs text-stone-500">No Japanese voice was found in this browser; audio may use a default voice or be unavailable.</p>}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={profile.show_furigana} onChange={(e) => update({ show_furigana: e.target.checked })} /> Show readings (furigana) by default</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={profile.show_romaji} onChange={(e) => update({ show_romaji: e.target.checked })} /> Show romaji by default</label>
        </Card>
        <Card className="space-y-2 text-sm">
          <h2 className="font-semibold">Services</h2>
          {capabilities ? (
            <>
              <p>AI tutor: {capabilities.ai_provider === "none" ? "not configured" : <AiBadge isMock={capabilities.ai_is_mock} provider={capabilities.ai_model ?? undefined} />}</p>
              <p>Speech: your browser&apos;s built-in text-to-speech and speech recognition. Recordings stay on your device.</p>
              <p>Sign-in: {capabilities.auth_mode === "supabase" ? "Supabase" : "local development accounts"}</p>
            </>
          ) : <p>Unavailable</p>}
        </Card>
        <Card className="space-y-3 border-red-200">
          <h2 className="font-semibold text-red-700">Delete account</h2>
          <p className="text-sm text-stone-600">Permanently deletes your profile, progress, reviews and conversation history.</p>
          {confirmDelete ? (
            <div className="flex gap-2"><Button variant="danger" onClick={deleteAccount}>Yes, delete everything</Button><Button variant="ghost" onClick={() => setConfirmDelete(false)}>Cancel</Button></div>
          ) : <Button variant="secondary" onClick={() => setConfirmDelete(true)}>Delete my account</Button>}
        </Card>
      </div>
    </AppShell>
  );
}
