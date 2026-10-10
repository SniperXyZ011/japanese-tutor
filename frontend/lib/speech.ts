"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export function speechSynthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function japaneseVoices(): SpeechSynthesisVoice[] {
  if (!speechSynthesisSupported()) return [];
  return window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith("ja"));
}

export function useJapaneseVoices(): SpeechSynthesisVoice[] {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  useEffect(() => {
    if (!speechSynthesisSupported()) return;
    const update = () => setVoices(japaneseVoices());
    update();
    window.speechSynthesis.addEventListener("voiceschanged", update);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", update);
  }, []);
  return voices;
}

export function speak(
  text: string,
  { rate = 1, voiceName, onEnd }: { rate?: number; voiceName?: string | null; onEnd?: () => void } = {},
): boolean {
  if (!speechSynthesisSupported()) return false;
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "ja-JP";
  u.rate = rate;
  const voices = japaneseVoices();
  const voice = voices.find((v) => v.name === voiceName) ?? voices[0];
  if (voice) u.voice = voice;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  synth.speak(u);
  return true;
}

export function stopSpeaking() {
  if (speechSynthesisSupported()) window.speechSynthesis.cancel();
}

// Minimal typings for the Web Speech recognition API (not in lib.dom for all TS versions).
interface RecognitionResultEvent {
  resultIndex: number;
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string; confidence: number } }>;
}
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: RecognitionResultEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
}

function recognitionCtor(): (new () => Recognition) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null) as (new () => Recognition) | null;
}

export function speechRecognitionSupported(): boolean {
  return recognitionCtor() !== null;
}

export type RecorderState = "idle" | "requesting" | "listening" | "processing" | "done" | "error";

const ERROR_MESSAGES: Record<string, string> = {
  "not-allowed": "Microphone access was blocked. Allow it in your browser settings, or type your answer.",
  "service-not-allowed": "Speech recognition isn't allowed in this browser. You can type your answer instead.",
  "no-speech": "We didn't hear anything. Try again a little closer to the microphone.",
  "audio-capture": "No microphone was found.",
  network: "Speech recognition needs an internet connection in this browser.",
};

/** Browser speech recognition (ja-JP) plus a local MediaRecorder copy for self-playback. */
export function useSpeechRecorder(maxSeconds = 30) {
  const [state, setState] = useState<RecorderState>("idle");
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const recRef = useRef<Recognition | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const finalRef = useRef("");
  const supported = speechRecognitionSupported();

  const cleanup = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    if (mediaRef.current && mediaRef.current.state !== "inactive") mediaRef.current.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const stop = useCallback(() => {
    if (recRef.current) {
      setState("processing");
      recRef.current.stop();
    }
    cleanup();
  }, [cleanup]);

  const start = useCallback(async () => {
    const Ctor = recognitionCtor();
    setError(null);
    setTranscript("");
    setInterim("");
    finalRef.current = "";
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    if (!Ctor) {
      setState("error");
      setError("Speech recognition isn't supported in this browser. Try Chrome or Edge, or type your answer.");
      return;
    }
    setState("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      if (typeof MediaRecorder !== "undefined") {
        const chunks: Blob[] = [];
        const mr = new MediaRecorder(stream);
        mr.ondataavailable = (e) => e.data.size && chunks.push(e.data);
        mr.onstop = () => {
          if (chunks.length) setAudioUrl(URL.createObjectURL(new Blob(chunks, { type: mr.mimeType })));
        };
        mr.start();
        mediaRef.current = mr;
      }
    } catch {
      setState("error");
      setError(ERROR_MESSAGES["not-allowed"]);
      return;
    }
    const rec = new Ctor();
    rec.lang = "ja-JP";
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    rec.onresult = (e) => {
      let interimText = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalRef.current += r[0].transcript;
        else interimText += r[0].transcript;
      }
      setInterim(interimText);
    };
    rec.onerror = (e) => {
      if (e.error === "aborted") return;
      setError(ERROR_MESSAGES[e.error] ?? "Speech recognition failed. Please try again.");
      setState("error");
      cleanup();
    };
    rec.onend = () => {
      cleanup();
      const text = (finalRef.current || "").trim();
      setInterim("");
      setTranscript(text);
      setState((s) => (s === "error" ? s : text ? "done" : "error"));
      if (!text) setError((prev) => prev ?? ERROR_MESSAGES["no-speech"]);
      recRef.current = null;
    };
    recRef.current = rec;
    setElapsed(0);
    timerRef.current = setInterval(() => {
      setElapsed((s) => {
        if (s + 1 >= maxSeconds) rec.stop();
        return s + 1;
      });
    }, 1000);
    rec.start();
    setState("listening");
  }, [audioUrl, cleanup, maxSeconds]);

  const reset = useCallback(() => {
    recRef.current?.abort();
    cleanup();
    setState("idle");
    setTranscript("");
    setInterim("");
    setError(null);
  }, [cleanup]);

  useEffect(() => () => {
    recRef.current?.abort();
    cleanup();
  }, [cleanup]);

  return { supported, state, transcript, interim, error, audioUrl, elapsed, start, stop, reset, setTranscript };
}
