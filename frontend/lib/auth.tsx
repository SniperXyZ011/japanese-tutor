"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import { authMode, getSupabase } from "./supabase";
import type { Capabilities, Profile } from "./types";

interface AuthState {
  profile: Profile | null;
  capabilities: Capabilities | null;
  loading: boolean;
  mode: "local" | "supabase";
  refresh: () => Promise<Profile | null>;
  setProfile: (p: Profile) => void;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<{ needsConfirmation: boolean }>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const p = await api<Profile>("/me");
      setProfile(p);
      return p;
    } catch (e) {
      if (!(e instanceof ApiError) || e.status !== 401) console.warn("profile load failed");
      setProfile(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    api<Capabilities>("/capabilities").then(setCapabilities).catch(() => setCapabilities(null));
    refresh();
    const sb = getSupabase();
    if (!sb) return;
    const { data } = sb.auth.onAuthStateChange(() => {
      refresh();
    });
    return () => data.subscription.unsubscribe();
  }, [refresh]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const sb = getSupabase();
      if (sb) {
        const { error } = await sb.auth.signInWithPassword({ email, password });
        if (error) throw new ApiError(error.message, 401, "invalid_credentials");
      } else {
        await api("/auth/login", { body: { email, password } });
      }
      await refresh();
    },
    [refresh],
  );

  const signUp = useCallback(
    async (email: string, password: string) => {
      const sb = getSupabase();
      if (sb) {
        const { data, error } = await sb.auth.signUp({ email, password });
        if (error) throw new ApiError(error.message, 400, "signup_failed");
        if (!data.session) return { needsConfirmation: true };
      } else {
        await api("/auth/signup", { body: { email, password } });
      }
      await refresh();
      return { needsConfirmation: false };
    },
    [refresh],
  );

  const signOut = useCallback(async () => {
    const sb = getSupabase();
    if (sb) await sb.auth.signOut();
    else await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    setProfile(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ profile, capabilities, loading, mode: authMode, refresh, setProfile, signIn, signUp, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
