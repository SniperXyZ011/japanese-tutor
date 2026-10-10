"use client";

import clsx from "clsx";
import { Volume2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { speak, speechSynthesisSupported, stopSpeaking } from "@/lib/speech";

export function AudioButton({
  text,
  rate,
  label = "Play audio",
  size = "md",
  autoPlay = false,
}: {
  text: string;
  rate?: number;
  label?: string;
  size?: "sm" | "md" | "lg";
  autoPlay?: boolean;
}) {
  const { profile } = useAuth();
  const [playing, setPlaying] = useState(false);
  const [supported, setSupported] = useState(true);
  const effectiveRate = rate ?? profile?.playback_speed ?? 1;

  const play = () => {
    const ok = speak(text, { rate: effectiveRate, voiceName: profile?.voice_name, onEnd: () => setPlaying(false) });
    setPlaying(ok);
    if (!ok) setSupported(false);
  };

  useEffect(() => {
    setSupported(speechSynthesisSupported());
    if (autoPlay && speechSynthesisSupported()) {
      const t = setTimeout(play, 250);
      return () => {
        clearTimeout(t);
        stopSpeaking();
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, autoPlay]);

  if (!supported)
    return <span className="text-xs text-stone-500">Audio isn&apos;t supported in this browser.</span>;

  return (
    <button
      type="button"
      onClick={play}
      aria-label={label}
      title={label}
      className={clsx(
        "inline-flex items-center justify-center rounded-full border border-brand/30 bg-brand-soft text-brand transition hover:bg-brand hover:text-white",
        size === "sm" && "h-8 w-8",
        size === "md" && "h-10 w-10",
        size === "lg" && "h-14 w-14",
        playing && "animate-pulse",
      )}
    >
      <Volume2 className={size === "lg" ? "h-6 w-6" : "h-4 w-4"} aria-hidden />
    </button>
  );
}
