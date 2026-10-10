import clsx from "clsx";
import { CheckCircle2, CircleHelp, Info, XCircle } from "lucide-react";
import type { Evaluation } from "@/lib/types";
import { AiBadge } from "./ui";

export function FeedbackCard({ evaluation }: { evaluation: Evaluation }) {
  const v = evaluation.verdict;
  const Icon = v === "correct" ? CheckCircle2 : v === "almost" ? Info : v === "unverified" ? CircleHelp : XCircle;
  return (
    <div
      role="status"
      aria-live="polite"
      className={clsx(
        "space-y-2 rounded-2xl border p-4",
        v === "correct" && "border-emerald-200 bg-emerald-50",
        v === "almost" && "border-amber-200 bg-amber-50",
        v === "incorrect" && "border-red-200 bg-red-50",
        v === "unverified" && "border-stone-200 bg-stone-50",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Icon
          className={clsx(
            "h-5 w-5",
            v === "correct" && "text-emerald-600",
            v === "almost" && "text-amber-600",
            v === "incorrect" && "text-red-600",
          )}
          aria-hidden
        />
        <p className="font-semibold">{evaluation.feedback}</p>
        {(evaluation.evaluator === "ai" || evaluation.evaluator === "mock_ai") && (
          <AiBadge isMock={evaluation.evaluator === "mock_ai"} />
        )}
      </div>
      {evaluation.corrected_answer && !evaluation.is_correct && (
        <p>
          <span className="text-sm text-stone-600">Correct answer: </span>
          <span lang="ja" className="jp text-lg font-semibold">{evaluation.corrected_answer}</span>
        </p>
      )}
      {evaluation.accepted_alternative && evaluation.expected_answers[0] && (
        <p className="text-sm text-stone-700">
          Also accepted. The model answer is <span lang="ja" className="jp font-semibold">{evaluation.expected_answers[0]}</span>.
        </p>
      )}
      {evaluation.meaning && <p className="text-sm"><b>Meaning:</b> {evaluation.meaning}</p>}
      {evaluation.grammar && <p className="text-sm"><b>Grammar:</b> {evaluation.grammar}</p>}
      {evaluation.naturalness && <p className="text-sm"><b>Naturalness:</b> {evaluation.naturalness}</p>}
      {evaluation.explanation && <p className="text-sm text-stone-700">{evaluation.explanation}</p>}
      {evaluation.follow_up && <p className="text-sm italic text-stone-600">Try next: {evaluation.follow_up}</p>}
      {evaluation.transcript_note && <p className="text-xs text-stone-500">{evaluation.transcript_note}</p>}
      {evaluation.evaluator !== "deterministic" && evaluation.confidence < 0.6 && (
        <p className="text-xs text-stone-500">Low-confidence check — treat this feedback as a suggestion.</p>
      )}
    </div>
  );
}
