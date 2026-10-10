# Kotoba Tutor — AI Japanese tutor (MVP)

A web app that teaches Japanese to English speakers from zero to roughly JLPT N5: listening, speaking, reading,
writing, vocabulary and grammar, with onboarding, an adaptive placement check, a curated curriculum, answer
evaluation, mastery tracking, spaced-repetition review and an AI conversation partner.

| Layer | Tech |
| --- | --- |
| Frontend | Next.js 15 (App Router), React 19, TypeScript, Tailwind v4 |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2, Alembic (Python 3.12) |
| Database | PostgreSQL (local Docker or Supabase) |
| Auth | Local email/password (dev) or Supabase Auth (JWT verified server-side) |
| AI | OpenRouter (`google/gemini-2.5-flash` by default), labelled mock provider for dev/tests |
| Speech | Browser Web Speech APIs (SpeechSynthesis + SpeechRecognition `ja-JP`) |

## What works

- **Onboarding** (10 questions) → **adaptive placement** (per-skill staircase over 25 curated items, ~8–18 questions) → recommended start unit with per-skill estimates and confidence.
- **Curriculum**: 6 units / 13 lessons / 89 exercises / 76 vocabulary / 16 grammar points in `backend/app/content` (validated on seed; prerequisites, concept references and answer keys are checked).
- **Lesson player**: Japanese text, reading, romaji toggle, translation, audio at normal/slow speed, multiple choice, listening, translation both ways, typed Japanese, sentence ordering, speaking. Resume mid-lesson.
- **Evaluation**: deterministic first (kana/punctuation/width normalisation, accepted alternatives, near-miss = "almost"); open answers go to the AI evaluator with structured, validated output; failures yield an explicit *unverified* result, never a fake "correct".
- **Speaking**: browser speech recognition with live transcript, self-playback, retry and "type instead" fallback. Feedback is labelled as transcript-based — no pronunciation scoring is claimed.
- **Mastery & SRS**: per concept × skill mastery (confidence-weighted, hints reduce credit, one mistake doesn't wipe progress); SM-2-style review queue (again/hard/good/easy, 10-minute relearning).
- **Speaking room**: AI tutor conversations at the learner's level with corrections, vocabulary notes, translation on demand, and an end-of-session recap. Persisted history.
- **Progress**: lessons, accuracy, study time, streak, daily goal, per-skill mastery, recent mistakes, history.
- **Settings**: playback speed, Japanese voice, furigana/romaji defaults, daily goal, retake placement, account deletion.

## Run locally

```bash
docker compose up -d db                      # Postgres on :5432

cd backend
cp .env.example .env                         # add OPENROUTER_API_KEY for real AI (optional)
uv venv -p 3.12 && uv pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --reload --port 8000

cd ../frontend
cp .env.example .env.local
npm install && npm run dev                   # http://localhost:3000 (proxies /api/v1 to :8000)
```

Or everything in Docker: `cp backend/.env.example backend/.env && docker compose up --build`.

Without `OPENROUTER_API_KEY` in development the backend uses a **mock tutor**, and the UI shows a
"Mock AI (development)" badge. In production without a key, AI features return `503 ai_unavailable`
while lessons, review and progress keep working.

## Using Supabase

1. Backend `.env`: `AUTH_MODE=supabase`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, optionally `SUPABASE_JWT_SECRET` (otherwise JWKS / `/auth/v1/user` is used), `SUPABASE_SERVICE_ROLE_KEY` (server-only, for account deletion), and `DATABASE_URL` = the Supabase connection string. Use the **pooler** string (Project Settings → Database → Connection pooling) if your host has no IPv6. Passwords with special characters are encoded automatically.
2. Frontend: `NEXT_PUBLIC_AUTH_MODE=supabase`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
3. `alembic upgrade head` — migration `0002` enables RLS with owner-only policies when it detects Supabase.

## Tests

```bash
cd backend && .venv/bin/pytest -q          # 45 tests; uses local Postgres + mock AI, no paid calls
cd backend && .venv/bin/ruff check app tests
cd frontend && npm test && npm run typecheck && npm run lint
# e2e (backend started with AI_PROVIDER=mock, frontend on :3000):
cd frontend && npx playwright install chromium && npm run e2e
```

## API

All endpoints are under `/api/v1` (OpenAPI at `/docs`). Errors use
`{"error": {"code", "message", "details", "request_id"}}`. Main groups: `auth`, `me`, `recommendation`,
`curriculum`, `lessons`, `exercises`, `assessment`, `review`, `progress`, `history`, `conversations`,
`explain`, `audio`.

## Security notes

- API keys stay on the server; the frontend only talks to `/api/v1` via the Next.js proxy.
- User identity always comes from the verified session/JWT, never from request bodies; every user-owned row is checked against it.
- AI usage is rate-limited per user (per minute and per day) and logged without prompt content.
- Request logs contain method, path, status, latency and a request id — no bodies or auth headers.

## Known limitations

- Speech uses browser APIs: quality and availability vary (best in Chrome/Edge); there's no server STT/TTS or pronunciation scoring yet. `app/services/audio` + `/audio/*` endpoints are the extension point.
- Placement is a short informal estimate, not an official JLPT result.
- Curriculum covers Units 0–5 (beginner/N5 foundations).
