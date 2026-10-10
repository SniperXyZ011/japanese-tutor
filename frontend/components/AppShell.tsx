"use client";

import clsx from "clsx";
import { BarChart3, BookOpen, Home, LogOut, MessageCircle, Repeat, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Spinner } from "./ui";

const NAV = [
  { href: "/dashboard", label: "Home", icon: Home },
  { href: "/learn", label: "Learn", icon: BookOpen },
  { href: "/review", label: "Review", icon: Repeat },
  { href: "/speak", label: "Speak", icon: MessageCircle },
  { href: "/progress", label: "Progress", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children, requireOnboarding = true }: { children: React.ReactNode; requireOnboarding?: boolean }) {
  const { profile, loading, signOut } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!profile) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    else if (requireOnboarding && !profile.onboarding_completed) router.replace("/onboarding");
  }, [loading, profile, requireOnboarding, router, pathname]);

  if (loading || !profile || (requireOnboarding && !profile.onboarding_completed)) return <Spinner />;

  return (
    <div className="min-h-screen pb-20 md:pb-0">
      <header className="sticky top-0 z-20 border-b border-stone-200 bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <Link href="/dashboard" className="flex items-center gap-2 font-bold">
            <span lang="ja" className="jp flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-white">言</span>
            <span>Kotoba Tutor</span>
          </Link>
          <nav className="hidden gap-1 md:flex" aria-label="Main">
            {NAV.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={clsx(
                  "rounded-lg px-3 py-1.5 text-sm font-medium",
                  pathname.startsWith(href) ? "bg-brand-soft text-brand" : "text-stone-600 hover:bg-stone-100",
                )}
              >
                {label}
              </Link>
            ))}
          </nav>
          <button
            onClick={async () => {
              await signOut();
              router.replace("/login");
            }}
            className="flex items-center gap-1 text-sm text-stone-500 hover:text-ink"
          >
            <LogOut className="h-4 w-4" aria-hidden /> <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
      <nav className="fixed inset-x-0 bottom-0 z-20 flex justify-around border-t border-stone-200 bg-white py-2 md:hidden" aria-label="Main mobile">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href} className={clsx("flex flex-col items-center text-xs", pathname.startsWith(href) ? "text-brand" : "text-stone-500")}>
            <Icon className="h-5 w-5" aria-hidden />
            {label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
