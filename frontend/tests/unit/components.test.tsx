import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FeedbackCard } from "@/components/FeedbackCard";
import { Recorder } from "@/components/Recorder";
import { ErrorBanner } from "@/components/ui";
import type { Evaluation } from "@/lib/types";

const base: Evaluation = {
  is_correct: false, score: 0.3, verdict: "incorrect", feedback: "Not quite.", corrected_answer: "がくせいです",
  expected_answers: ["がくせいです"], explanation: "です follows the noun.", accepted_alternative: false,
  meaning: null, grammar: null, naturalness: null, confidence: 1, evaluator: "deterministic",
  transcript_note: null, follow_up: null,
};

describe("FeedbackCard", () => {
  it("shows the correction for wrong answers", () => {
    render(<FeedbackCard evaluation={base} />);
    expect(screen.getByText("Not quite.")).toBeInTheDocument();
    expect(screen.getByText("がくせいです")).toBeInTheDocument();
  });
  it("labels mock AI feedback and transcript notes", () => {
    render(<FeedbackCard evaluation={{ ...base, evaluator: "mock_ai", confidence: 0.4, transcript_note: "Checked against a speech-recognition transcript." }} />);
    expect(screen.getByText(/Mock AI/)).toBeInTheDocument();
    expect(screen.getByText(/speech-recognition transcript/)).toBeInTheDocument();
    expect(screen.getByText(/Low-confidence/)).toBeInTheDocument();
  });
});

describe("Recorder", () => {
  beforeEach(() => {
    delete (window as unknown as Record<string, unknown>).SpeechRecognition;
    delete (window as unknown as Record<string, unknown>).webkitSpeechRecognition;
  });
  it("falls back to typing when speech recognition is unsupported", () => {
    const onSubmit = vi.fn();
    render(<Recorder onSubmit={onSubmit} />);
    expect(screen.getByText(/isn.t available in this browser/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Type your answer/), { target: { value: "こんにちは" } });
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(onSubmit).toHaveBeenCalledWith("こんにちは", "typed");
  });
});

describe("ErrorBanner", () => {
  it("offers retry", () => {
    const retry = vi.fn();
    render(<ErrorBanner message="Server down" onRetry={retry} />);
    fireEvent.click(screen.getByText("Retry"));
    expect(retry).toHaveBeenCalled();
  });
});
