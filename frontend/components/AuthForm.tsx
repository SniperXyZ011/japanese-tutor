"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Card, ErrorBanner } from "./ui";

export function AuthForm({ kind }: { kind: "login" | "signup" }) {
  const { signIn, signUp } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) return setError("Password must be at least 8 characters.");
    setBusy(true);
    try {
      if (kind === "signup") {
        const r = await signUp(email, password);
        if (r.needsConfirmation) {
          setInfo("Check your email to confirm your account, then sign in.");
          return;
        }
        router.replace("/onboarding");
      } else {
        await signIn(email, password);
        const next = params.get("next");
        router.replace(next && next.startsWith("/") ? next : "/dashboard");
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <Link href="/" lang="ja" className="jp mb-6 text-center text-3xl font-bold text-brand">ことば</Link>
      <Card>
        <h1 className="mb-4 text-xl font-bold">{kind === "login" ? "Welcome back" : "Create your account"}</h1>
        <form onSubmit={submit} className="space-y-4">
          <label className="block text-sm font-medium">
            Email
            <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-xl border border-stone-300 px-3 py-2 focus:border-brand focus:outline-none" />
          </label>
          <label className="block text-sm font-medium">
            Password
            <input type="password" required minLength={8} autoComplete={kind === "login" ? "current-password" : "new-password"}
              value={password} onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-xl border border-stone-300 px-3 py-2 focus:border-brand focus:outline-none" />
          </label>
          {error && <ErrorBanner message={error} />}
          {info && <p className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800">{info}</p>}
          <Button type="submit" loading={busy} className="w-full">
            {kind === "login" ? "Sign in" : "Sign up"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-stone-600">
          {kind === "login" ? (
            <>New here? <Link className="font-semibold text-brand" href="/signup">Create an account</Link></>
          ) : (
            <>Already have an account? <Link className="font-semibold text-brand" href="/login">Sign in</Link></>
          )}
        </p>
      </Card>
    </main>
  );
}
