import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const authMode: "local" | "supabase" =
  process.env.NEXT_PUBLIC_AUTH_MODE === "supabase" && url && anonKey ? "supabase" : "local";

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  if (authMode !== "supabase" || !url || !anonKey) return null;
  if (!client) client = createClient(url, anonKey);
  return client;
}

export async function getAccessToken(): Promise<string | null> {
  const sb = getSupabase();
  if (!sb) return null;
  const { data } = await sb.auth.getSession();
  return data.session?.access_token ?? null;
}
