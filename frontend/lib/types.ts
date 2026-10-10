export type Skill = "listening" | "speaking" | "vocabulary" | "grammar" | "reading" | "writing";
export type Level = "absolute_beginner" | "beginner" | "n5" | "n5_plus";

export interface Capabilities {
  auth_mode: "local" | "supabase";
  ai_provider: "openrouter" | "mock" | "none";
  ai_model: string | null;
  ai_is_mock: boolean;
  tts_provider: string;
  stt_provider: string;
  max_recording_seconds: number;
  max_conversation_turns: number;
}

export interface OnboardingAnswers {
  prior_experience?: "none" | "some_self_study" | "classes" | "lived_in_japan" | null;
  hiragana?: "none" | "some" | "fluent" | null;
  katakana?: "none" | "some" | "fluent" | null;
  kanji?: "none" | "few" | "n5" | "n4_plus" | null;
  listening?: "none" | "basic_phrases" | "slow_conversation" | "everyday" | null;
  speaking_confidence?: "none" | "low" | "medium" | "high" | null;
  vocab_grammar?: "none" | "basic" | "n5" | "n4_plus" | null;
  goals: string[];
  explanation_language?: "en";
  daily_minutes?: number | null;
  conversation_balance?: "more_structured" | "balanced" | "more_conversation" | null;
}

export interface Profile {
  id: string;
  email: string | null;
  display_name: string | null;
  onboarding: Partial<OnboardingAnswers>;
  onboarding_completed: boolean;
  current_level: Level | null;
  start_unit_id: string | null;
  explanation_language: string;
  daily_goal_minutes: number;
  playback_speed: number;
  show_furigana: boolean;
  show_romaji: boolean;
  voice_name: string | null;
  streak_days: number;
}

export interface LessonSummary {
  id: string;
  unit_id: string;
  position: number;
  title: string;
  summary: string;
  difficulty: number;
  estimated_minutes: number;
  status: "not_started" | "in_progress" | "completed";
  best_score: number | null;
  locked: boolean;
}

export interface Unit {
  id: string;
  position: number;
  title: string;
  description: string;
  level: string;
  lessons: LessonSummary[];
}

export interface Vocabulary {
  id: string;
  japanese: string;
  reading: string;
  romaji: string;
  meaning: string;
  part_of_speech: string;
  example_ja: string | null;
  example_en: string | null;
}

export interface Grammar {
  id: string;
  name: string;
  pattern: string;
  explanation: string;
  examples: { japanese: string; reading?: string; english: string }[];
}

export type ExerciseType =
  | "presentation"
  | "multiple_choice"
  | "listening_choice"
  | "ja_to_en"
  | "en_to_ja"
  | "typed_japanese"
  | "sentence_completion"
  | "sentence_ordering"
  | "speaking";

export interface Exercise {
  id: string;
  position: number;
  type: ExerciseType;
  skill: Skill;
  instructions: string;
  prompt_ja: string | null;
  prompt_reading: string | null;
  prompt_romaji: string | null;
  prompt_en: string | null;
  audio_text: string | null;
  choices: string[];
  hints: string[];
  meta: Record<string, unknown>;
}

export interface LessonDetail {
  id: string;
  unit_id: string;
  title: string;
  summary: string;
  objectives: string[];
  prerequisites: string[];
  difficulty: number;
  estimated_minutes: number;
  pass_score: number;
  vocabulary: Vocabulary[];
  grammar: Grammar[];
  exercises: Exercise[];
  status: string;
  attempt_id: string | null;
  current_step: number;
}

export interface Recommendation {
  kind: "review" | "lesson" | "assessment" | "onboarding" | "complete";
  reason: string;
  lesson: LessonSummary | null;
  due_reviews: number;
  weak_concepts: string[];
}

export interface Evaluation {
  is_correct: boolean;
  score: number;
  verdict: "correct" | "almost" | "incorrect" | "unverified";
  feedback: string;
  corrected_answer: string | null;
  expected_answers: string[];
  explanation: string | null;
  accepted_alternative: boolean;
  meaning: string | null;
  grammar: string | null;
  naturalness: string | null;
  confidence: number;
  evaluator: "deterministic" | "ai" | "mock_ai" | "fallback";
  transcript_note: string | null;
  follow_up: string | null;
}

export interface AttemptResult {
  attempt_id: string;
  evaluation: Evaluation;
  mastery_updates: { concept_id: string; skill: string; mastery: number }[];
  current_step: number | null;
}

export interface LessonComplete {
  attempt_id: string;
  score: number;
  passed: boolean;
  exercises_answered: number;
  next: Recommendation;
}

export interface AssessmentItem {
  id: string;
  skill: Skill;
  difficulty: number;
  type: string;
  instructions: string;
  prompt_ja: string | null;
  prompt_en: string | null;
  audio_text: string | null;
  choices: string[];
}

export interface AssessmentProgress {
  assessment_id: string;
  status: string;
  answered: number;
  estimated_total: number;
  next_item: AssessmentItem | null;
}

export interface PlacementResult {
  assessment_id: string;
  recommended_level: Level;
  recommended_level_label: string;
  recommended_unit_id: string;
  skills: { skill: Skill; score: number; confidence: number; items: number }[];
  strengths: string[];
  weak_areas: string[];
  explanation: string;
  completed_at: string | null;
  disclaimer: string;
}

export interface ReviewCard {
  id: string;
  concept_id: string;
  concept_type: string;
  state: string;
  due_at: string;
  from_mistake: boolean;
  front: string;
  reading: string | null;
  meaning: string;
  detail: string | null;
  audio_text: string | null;
}

export interface VocabNote {
  japanese: string;
  reading?: string | null;
  meaning: string;
}

export interface TutorContent {
  japanese?: string;
  reading?: string | null;
  english?: string;
  correction?: { has_error: boolean; corrected: string | null; explanation: string | null };
  new_vocabulary?: VocabNote[];
  follow_up_hint?: string | null;
  is_mock?: boolean;
}

export interface Turn {
  id: string;
  position: number;
  role: "tutor" | "learner";
  text: string;
  input_mode: string | null;
  content: TutorContent;
  created_at: string;
}

export interface Conversation {
  id: string;
  topic: string;
  mode: string;
  status: string;
  turn_count: number;
  provider: string;
  summary: Recap | null;
  created_at: string;
  completed_at: string | null;
}

export interface ConversationDetail extends Conversation {
  turns: Turn[];
  turns_total: number;
}

export interface Recap {
  summary: string;
  strengths: string[];
  improvements: string[];
  vocabulary: VocabNote[];
}

export interface ProgressSummary {
  lessons_completed: number;
  lessons_total: number;
  exercises_answered: number;
  accuracy: number | null;
  learning_minutes: number;
  minutes_today: number;
  daily_goal_minutes: number;
  streak_days: number;
  reviews_due: number;
  reviews_completed: number;
  current_level: Level | null;
  concepts_needing_practice: { concept_id: string; skill: string; mastery: number }[];
  recent_mistakes: { exercise_id: string; instructions: string; answer: string; expected: string | null; skill: string; created_at: string }[];
}

export interface SkillProgress {
  skill: Skill;
  accuracy: number | null;
  attempts: number;
  mastery: number | null;
  placement_score: number | null;
}

export interface HistoryItem {
  kind: "exercise" | "lesson" | "conversation" | "review";
  title: string;
  detail: string | null;
  is_correct: boolean | null;
  created_at: string;
}

export const LEVEL_LABELS: Record<Level, string> = {
  absolute_beginner: "Absolute beginner",
  beginner: "Beginner (early N5)",
  n5: "Upper beginner (N5)",
  n5_plus: "Late beginner (N5+)",
};
