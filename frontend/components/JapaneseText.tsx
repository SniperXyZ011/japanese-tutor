"use client";

import clsx from "clsx";

/** Japanese line with optional reading (shown above as furigana-style line), romaji and translation. */
export function JapaneseText({
  ja,
  reading,
  romaji,
  en,
  showReading = true,
  showRomaji = false,
  showTranslation = true,
  size = "lg",
}: {
  ja: string;
  reading?: string | null;
  romaji?: string | null;
  en?: string | null;
  showReading?: boolean;
  showRomaji?: boolean;
  showTranslation?: boolean;
  size?: "md" | "lg" | "xl";
}) {
  const showR = showReading && reading && reading !== ja;
  return (
    <div className="space-y-1">
      {showR && <p className="jp text-sm text-stone-500" lang="ja">{reading}</p>}
      <p
        lang="ja"
        className={clsx("jp font-semibold text-ink", size === "md" && "text-xl", size === "lg" && "text-3xl", size === "xl" && "text-5xl")}
      >
        {ja}
      </p>
      {showRomaji && romaji && <p className="text-sm italic text-stone-500">{romaji}</p>}
      {showTranslation && en && <p className="text-stone-700">{en}</p>}
    </div>
  );
}
