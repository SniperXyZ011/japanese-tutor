import uuid

from app.models import ApiUsageLog


def test_health(client):
    assert client.get("/health").json()["database"] == "ok"


def test_protected_routes_require_auth(client):
    for path in ("/api/v1/me", "/api/v1/curriculum", "/api/v1/review", "/api/v1/progress"):
        r = client.get(path)
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"
        assert r.json()["error"]["request_id"]


def test_signup_login_and_duplicate(client):
    email = f"d{uuid.uuid4().hex[:8]}@example.com"
    assert client.post("/api/v1/auth/signup", json={"email": email, "password": "password123"}).status_code == 201
    assert client.post("/api/v1/auth/signup", json={"email": email, "password": "password123"}).status_code == 409
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "wrongpass1"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "password123"}).status_code == 200
    client.delete("/api/v1/me")


def test_validation_error_shape(user_client):
    r = user_client.patch("/api/v1/me", json={"daily_goal_minutes": 1000})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_recommendation_flow(user_client):
    assert user_client.get("/api/v1/recommendation").json()["kind"] == "onboarding"
    user_client.patch("/api/v1/me", json={"onboarding": {"goals": []}, "onboarding_completed": True})
    assert user_client.get("/api/v1/recommendation").json()["kind"] == "assessment"


def test_lesson_vertical_slice_persists(onboarded, db):
    rec = onboarded.get("/api/v1/recommendation").json()
    assert rec["kind"] == "lesson"
    lesson_id = rec["lesson"]["id"]
    lesson = onboarded.get(f"/api/v1/lessons/{lesson_id}").json()
    attempt = onboarded.post(f"/api/v1/lessons/{lesson_id}/start").json()["attempt_id"]
    graded = [e for e in lesson["exercises"] if e["type"] != "presentation"]
    wrong = graded[0]
    r = onboarded.post(f"/api/v1/exercises/{wrong['id']}/attempt",
                       json={"answer": "zzz", "lesson_attempt_id": attempt}).json()
    assert r["evaluation"]["is_correct"] is False
    q = onboarded.get("/api/v1/review").json()
    assert q["due_count"] == 0  # relearning is scheduled ~10 minutes out
    upcoming = onboarded.get("/api/v1/review/upcoming").json()
    assert upcoming["total"] >= 1
    done = onboarded.post(f"/api/v1/lessons/{lesson_id}/complete",
                          json={"attempt_id": attempt, "active_seconds": 120}).json()
    assert done["passed"] is False
    progress = onboarded.get("/api/v1/progress").json()
    assert progress["exercises_answered"] == 1 and progress["streak_days"] == 1
    curriculum = onboarded.get("/api/v1/curriculum").json()
    status = {le["id"]: le["status"] for u in curriculum for le in u["lessons"]}
    assert status[lesson_id] == "completed"


def test_cannot_use_other_users_attempt(onboarded, client):
    attempt = onboarded.post("/api/v1/lessons/u0-l1/start").json()["attempt_id"]
    other = client
    other.post("/api/v1/auth/signup", json={"email": f"o{uuid.uuid4().hex[:8]}@example.com", "password": "password123"})
    ex = onboarded.get("/api/v1/lessons/u0-l1").json()["exercises"]
    graded = next(e for e in ex if e["type"] != "presentation")
    r = other.post(f"/api/v1/exercises/{graded['id']}/attempt", json={"answer": "x", "lesson_attempt_id": attempt})
    assert r.status_code == 404
    other.delete("/api/v1/me")


def test_assessment_end_to_end(user_client):
    p = user_client.post("/api/v1/assessment/start", json={}).json()
    aid = p["assessment_id"]
    assert user_client.post(f"/api/v1/assessment/{aid}/answer",
                            json={"item_id": "not-current", "answer": "x"}).status_code == 409
    while p["next_item"]:
        p = user_client.post(f"/api/v1/assessment/{aid}/answer",
                             json={"item_id": p["next_item"]["id"], "skipped": True}).json()
    res = user_client.get(f"/api/v1/assessment/{aid}/result").json()
    assert res["recommended_level"] == "absolute_beginner"
    assert user_client.get("/api/v1/me").json()["start_unit_id"] == "unit-0"


def test_conversation_with_mock_ai(onboarded):
    c = onboarded.post("/api/v1/conversations", json={"topic": "hobbies"})
    assert c.status_code == 201
    cid = c.json()["id"]
    t = onboarded.post(f"/api/v1/conversations/{cid}/turns", json={"text": "わたしはアニメがすきです"}).json()
    assert t["is_mock"] is True and t["tutor_turn"]["role"] == "tutor"
    recap = onboarded.post(f"/api/v1/conversations/{cid}/finish").json()
    assert recap["is_mock"] is True
    assert onboarded.post(f"/api/v1/conversations/{cid}/turns", json={"text": "x"}).status_code == 409


def test_ai_rate_limit(onboarded, db, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "ai_requests_per_minute", 1)
    assert onboarded.post("/api/v1/explain", json={"text": "です"}).status_code == 200
    r = onboarded.post("/api/v1/explain", json={"text": "です"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
    assert db.query(ApiUsageLog).count() >= 1


def test_audio_upload_validation(onboarded):
    r = onboarded.post("/api/v1/audio/transcribe", files={"file": ("a.txt", b"x" * 200, "text/plain")})
    assert r.status_code == 415
    r = onboarded.post("/api/v1/audio/transcribe", files={"file": ("a.webm", b"x" * 10, "audio/webm")})
    assert r.status_code == 422
    r = onboarded.post("/api/v1/audio/tts", json={"text": "こんにちは"})
    assert r.json()["use_browser_fallback"] is True


def test_review_submit_reschedules(onboarded, db):
    from datetime import UTC, datetime, timedelta

    from app.models import ReviewItem
    ex = onboarded.get("/api/v1/lessons/u0-l1").json()["exercises"]
    graded = next(e for e in ex if e["type"] != "presentation")
    onboarded.post(f"/api/v1/exercises/{graded['id']}/attempt", json={"answer": "zzz"})
    me = onboarded.get("/api/v1/me").json()
    db.query(ReviewItem).filter(ReviewItem.user_id == uuid.UUID(me["id"])).update(
        {"due_at": datetime.now(UTC) - timedelta(minutes=1)})
    db.commit()
    q = onboarded.get("/api/v1/review").json()
    assert q["due_count"] >= 1
    r = onboarded.post("/api/v1/review", json={"review_id": q["items"][0]["id"], "grade": "good"}).json()
    assert datetime.fromisoformat(r["next_due_at"]) > datetime.now(UTC)


def test_delete_account_removes_data(user_client):
    assert user_client.delete("/api/v1/me").status_code == 204
    assert user_client.get("/api/v1/me").status_code == 401
